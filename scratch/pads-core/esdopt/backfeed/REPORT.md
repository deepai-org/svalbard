# Option A back-feed study: up-diodes from the custom signal pads to the ring supply (2026-11-18)

Simulation study only. No layout, no project edits, no commits. Work dir `scratch/pads-core/esdopt/backfeed/`
(`gen.py` writes decks to `out/`, `run.sh` runs them one at a time in the pinned container, `collect.py` parses logs).
Status of each section is written as it is finished. "SIM" = simulated here, "EST" = hand estimate, "READ" = taken
from an existing document without rerun.

## 0. Limits and acceptance criteria, declared BEFORE any run

| Id | Quantity | Limit | Source |
|---|---|---|---|
| L1 | Back-fed supply node, chip meant to be off | < 0.5 V: POR certainly re-armed (pass). 0.5-1.5 V: POR re-arm not guaranteed (marginal). > 1.5 V: POR sees no power cycle (fail) | core_support README: dips to <= 0.5 V re-issue reset, to 1.0 V in 5 of 8 cases, to >= 1.5 V never |
| L2 | dV/dt of the die supply caused by a partner edge | <= 0.3 V/us (board rule B52) pass; >= 0.91 V/us may fire. "Fired" = the gate of a clamp NMOS (`n4`) above 0.7 V | CLAMP.md |
| L3 | Current injected into one pad's p+/n-well diode | <= 100 mA (JESD78 class test level); the injection must not coincide with a supply that can sustain latch-up | task statement, README lu.json notes |
| L4a | Continuous current in one bond wire | <= 0.34 A | task statement (0.8 mil Al) |
| L4b | Continuous current per diode finger | <= 3.5 mA with the TLP-site via pattern (6 Via1 cuts on the supply terminal x 0.58 mA/cut at 85 C, DRM 14.2 as used by `verification/em_check.py`), i.e. 14 / 28 / 56 mA per pad for N = 4 / 8 / 16 | tlp_site.py, em_check.py |
| L5 | Supply node driven from a pad | <= 3.63 V | MANDATE section 2 |
| L6 | Bond-pad voltage in a positive zap (hybrid, section 5) | <= 8.0 V at 1.33 A (2 kV) and at 0.67 A (1 kV); devices 6.0 V screen not evaluated here | README section 4 |

Bench acceptance (known answers and negative controls):

| Bench | Known answer, tolerance | Negative control (must fail the check) |
|---|---|---|
| K0 single `diode_pd2nw_06v0` finger, 25 C | level-3 equation with Is = is*area + jsw*pj, n, ik*area, rs/area, solved in Python: within 3 % of current for 0.3-1.0 V | same check against the equation without the high-injection term must fail above the knee |
| B1 back-feed DC | (c) supply held: current equals K0 x N at the same junction voltage within 3 %; (a) floating: supply = pad - Vd(leak) | diodes removed: supply current must be < 1 nA and supply node < 10 mV; the "back-feed present" check must report none |
| B3b clamp firing | ring without the 8 uF, 50 V/us-class edge: clamps must fire (n4 > 0.7 V), as CLAMP.md stage A | same edge with the 8 uF present is the case under test |
| B3a POR | cold start 0 -> 3.3 V in 1 ms at tt/27: release 39.5 ms (audit `kn_tt_27_3.3_1ms`: 39.55 ms), within 3 % | none separate: the plateau cases are expected to show no reset pulse; the cold start shows that the bench can show one |
| B5 local clamp | 4 mm `nfet_06v0` with gate = drain = 3.3 V at tt/27: 0.92-1.0 A (CLAMP.md stage A, one provider cell) | gate grounded: must not reach 1.33 A at 8 V |

Assumptions fixed before the runs:
- Diode: PDK `diode_pd2nw_06v0`, area 22.5 um2, perimeter 51.8 um per finger (protection-primitives.json), N = 4 / 8 / 16 as `m`.
  The model is a two-terminal diode: all pad current goes to the n-well (supply). In silicon part of it goes to the
  substrate through the parasitic vertical PNP, so the supply current here is an upper bound and the substrate current is not modelled.
- Pad side series resistance 0.7 ohm (bond wire 0.25 ohm + pad-site riser 0.44 ohm, ESD-METAL.md `pad_tlp_flat`).
- Supply node: 8 dvdd + 10 dvss + 4 cor provider cells (transistor level), 8 uF, bond loop 22.5 mohm / 2.2 nH and 1 nF die capacitance in the fast transients.
- Unpowered-chip load, three points (resistor to VSS on the supply node): **6 kohm nominal** (always-on current at reset 0.55 mA at 3.3 V, always-on-audit section 6),
  **1.65 kohm heavy** (2.2 mA at 3.63 V: ff/85 with `aosc.EN` floating), **36 kohm light** (91 uA at 3.3 V: bandgap + VCM divider only).
  A resistor overstates the load below about 1 V (MOS circuits draw almost nothing there), so the "floating" case (a), provider-cell leakage only, is the bound for low voltages.
  Board loads on the die supply that exist on some carriers and are NOT included: 10 kohm RESET_N pull-up into an asserted supervisor (B49), regulator feedback divider / output discharge.
- (c) "regulator that sinks": 0.05 ohm to 0 V at the board node.
- Corners: MOS / diode typical unless stated; temperatures 0 / 27 / 85 C.

## K0. Single diode against the model equation (SIM, passed)

`out/k0_25.sp`, `k0.py`. One finger, 25 C (model `tref`), 0.30-1.00 V in 0.05 V steps: ngspice agrees with the level-3 equation
(Is = is x area + jsw x pj = 4.7e-18 + 8.3e-18 A, n = 1.0058, knee ik x area = 5.7 uA applied to the area component only, rs / area = 8.9 ohm)
within 0.1 % at all 15 points (limit 3 %). Negative control: the same equation without the knee term is outside 3 % at 9 of 15 points
(+38 % at 0.80 V), so the check does discriminate. Per finger: 3.3 nA at 0.50 V, 6.4 uA at 0.70 V, 0.24 mA at 0.80 V, 3.5 mA at 0.90 V,
11.3 mA at 1.00 V; above that the 8.9 ohm series resistance of the model sets the slope.

## 1. Current into the unpowered supply versus pad voltage (SIM, `out/b1_*`, `collect_b1.py`)

Stiff source at the board finger (0.7 ohm to the diode), one pad, sweep 0 to 5.25 V in 25 mV steps. All custom pads get the same diode in
option A, so the table is per pad for every family; what differs per pad is the partner (section 2). 3.625 V is the grid point next to 3.63 V.
The full 0 / 27 / 85 C x N = 4 / 8 / 16 x five-load tables are printed by `python3 collect_b1.py` (45 sweeps); the rows below are the bounding ones.
Known answer: case (c) at 27 C, N = 8 equals 8 x K0 at the same junction voltage (see K0b below). Negative control (`b1neg_27_8`, up-diode removed):
supply current <= 7 fA, floating supply node <= 1e-15 V: no back-feed reported, as required.

**(a) supply floating, provider-cell leakage only (22 cells: 0.4-2.8 nA at 0-27 C, 0.1-0.15 uA at 85 C). Supply node (V):**

| T (C) | N | pad 0.5 V | pad 0.7 V | pad 1.0 V | pad 2.0 V | pad 3.3 V | pad 3.625 V | pad 5.25 V |
|---|---|---|---|---|---|---|---|---|
| 0 | 4 | 0.07 | 0.18 | 0.56 | 1.53 | 2.82 | 3.14 | 4.76 |
| 0 | 16 | 0.10 | 0.19 | 0.59 | 1.57 | 2.85 | 3.18 | 4.79 |
| 27 | 4 | 0.09 | 0.19 | 0.58 | 1.57 | 2.86 | 3.18 | 4.80 |
| 27 | 16 | 0.11 | 0.33 | 0.62 | 1.60 | 2.89 | 3.22 | 4.83 |
| 85 | 4 | 0.10 | 0.32 | 0.62 | 1.60 | 2.89 | 3.21 | 4.83 |
| 85 | 16 | 0.12 | 0.36 | 0.66 | 1.65 | 2.93 | 3.26 | 4.87 |

The floating supply follows the pad at pad - 0.39..0.49 V (0 C: 0.46-0.49, 27 C: 0.41-0.45, 85 C: 0.38-0.42). N changes it by 17 mV per doubling.
A pad at 3.63 V lifts the supply to 3.14-3.26 V; a pad at 5.25 V lifts it to 4.76-4.87 V, above the 3.63 V limit L5.

**(b) supply loaded by the unpowered chip. Current into the pad / supply node:**

| Load | T (C) | N | pad 0.5 V | pad 0.7 V | pad 1.0 V | pad 2.0 V | pad 3.3 V | pad 3.625 V | pad 5.25 V |
|---|---|---|---|---|---|---|---|---|---|
| 36 kohm (light) | 0 | 4 | 0.93 nA / 0.00 V | 9.6e+02 nA / 0.03 V | 7.87 uA / 0.28 V | 34.6 uA / 1.25 V | 70.2 uA / 2.53 V | 79.2 uA / 2.85 V | 124 uA / 4.46 V |
| 36 kohm (light) | 27 | 8 | 31 nA / 0.00 V | 2.4 uA / 0.09 V | 9.7 uA / 0.35 V | 36.5 uA / 1.31 V | 72.1 uA / 2.59 V | 81 uA / 2.92 V | 126 uA / 4.53 V |
| 36 kohm (light) | 85 | 16 | 1.41 uA / 0.05 V | 5.75 uA / 0.21 V | 13.3 uA / 0.48 V | 40.2 uA / 1.44 V | 75.7 uA / 2.72 V | 84.7 uA / 3.04 V | 129 uA / 4.66 V |
| 6 kohm (nominal) | 0 | 4 | 0.93 nA / 0.00 V | 2.29 uA / 0.01 V | 40.4 uA / 0.24 V | 200 uA / 1.20 V | 414 uA / 2.48 V | 468 uA / 2.81 V | 736 uA / 4.42 V |
| 6 kohm (nominal) | 27 | 8 | 32 nA / 0.00 V | 8.69 uA / 0.05 V | 50.7 uA / 0.30 V | 211 uA / 1.26 V | 424 uA / 2.55 V | 478 uA / 2.87 V | 746 uA / 4.48 V |
| 6 kohm (nominal) | 85 | 16 | 3.53 uA / 0.02 V | 26.6 uA / 0.16 V | 70.9 uA / 0.42 V | 231 uA / 1.39 V | 444 uA / 2.66 V | 498 uA / 2.99 V | 766 uA / 4.60 V |
| 1.65 kohm (heavy) | 0 | 4 | 0.93 nA / 0.00 V | 3.22 uA / 0.01 V | 129 uA / 0.21 V | 709 uA / 1.17 V | 1.48 mA / 2.45 V | 1.68 mA / 2.77 V | 2.66 mA / 4.38 V |
| 1.65 kohm (heavy) | 27 | 8 | 32 nA / 0.00 V | 18.9 uA / 0.03 V | 165 uA / 0.27 V | 745 uA / 1.23 V | 1.52 mA / 2.51 V | 1.71 mA / 2.83 V | 2.69 mA / 4.44 V |
| 1.65 kohm (heavy) | 85 | 16 | 5.23 uA / 0.01 V | 74.8 uA / 0.12 V | 234 uA / 0.39 V | 815 uA / 1.34 V | 1.59 mA / 2.62 V | 1.78 mA / 2.94 V | 2.76 mA / 4.55 V |

With any plausible chip load the supply node still sits 0.65-0.85 V below the pad: 2.45-2.72 V for a 3.3 V pad, 2.77-3.04 V for 3.63 V,
4.38-4.66 V for 5.25 V. The chip load takes 0.07-1.8 mA; it cannot hold the node down. Diode dissipation is below 2.3 mW in every (a)/(b) case.

**(c) supply held at 0 V by a sinking regulator (0.05 ohm), stiff source. Current into the pad / diode power:**

| T (C) | N | pad 0.5 V | pad 0.7 V | pad 1.0 V | pad 2.0 V | pad 3.3 V | pad 3.625 V | pad 5.25 V |
|---|---|---|---|---|---|---|---|---|
| 0 | 4 | 0.93 nA / 0.46 nW | 4.01 uA / 2.81 uW | 28.4 mA / 27.8 mW | 355 mA / 615 mW | 800 mA / 2.16 W | 912 mA / 2.68 W | 1.47 A / 6.1 W |
| 0 | 8 | 1.9 nA / 0.93 nW | 8.02 uA / 5.61 uW | 47.4 mA / 45.7 mW | 566 mA / 892 mW | 1.27 A / 2.98 W | 1.45 A / 3.68 W | 2.34 A / 8.18 W |
| 0 | 16 | 3.7 nA / 1.9 nW | 16 uA / 11.2 uW | 72.2 mA / 68.3 mW | 807 mA / 1.13 W | 1.81 A / 3.51 W | 2.06 A / 4.28 W | 3.32 A / 9.16 W |
| 27 | 4 | 16 nA / 8 nW | 29.5 uA / 20.6 uW | 36.3 mA / 35.3 mW | 352 mA / 611 mW | 781 mA / 2.12 W | 889 mA / 2.63 W | 1.43 A / 5.98 W |
| 27 | 8 | 32 nA / 16 nW | 58.9 uA / 41.2 uW | 60.5 mA / 57.8 mW | 565 mA / 891 mW | 1.25 A / 2.96 W | 1.42 A / 3.64 W | 2.29 A / 8.09 W |
| 27 | 16 | 64 nA / 32 nW | 118 uA / 82.3 uW | 91.9 mA / 85.6 mW | 813 mA / 1.13 W | 1.79 A / 3.5 W | 2.04 A / 4.27 W | 3.27 A / 9.15 W |
| 85 | 4 | 1.72 uA / 8.6e+02 nW | 756 uA / 529 uW | 52.6 mA / 50.5 mW | 347 mA / 604 mW | 746 mA / 2.05 W | 847 mA / 2.53 W | 1.35 A / 5.72 W |
| 85 | 8 | 3.43 uA / 1.72 uW | 1.49 mA / 1.04 mW | 88 mA / 82.2 mW | 565 mA / 891 mW | 1.21 A / 2.9 W | 1.37 A / 3.57 W | 2.19 A / 7.9 W |
| 85 | 16 | 6.87 uA / 3.43 uW | 2.89 mA / 2.01 mW | 134 mA / 120 mW | 827 mA / 1.14 W | 1.76 A / 3.49 W | 2 A / 4.25 W | 3.18 A / 9.11 W |

N = 4, 27 C: 14 mA x N/4 finger limit (L4b: 14 mA) reached at pad 0.91 V, 100 mA (L3) at 1.22 V, 0.34 A (L4a) at 1.96 V.

N = 8, 27 C: 14 mA x N/4 finger limit (L4b: 28 mA) reached at pad 0.92 V, 100 mA (L3) at 1.09 V, 0.34 A (L4a) at 1.57 V.

N = 16, 27 C: 14 mA x N/4 finger limit (L4b: 56 mA) reached at pad 0.94 V, 100 mA (L3) at 1.01 V, 0.34 A (L4a) at 1.36 V.

A stiff source against a held supply is a short through the diode: the current is set by the model's 8.9 ohm / N series resistance plus 0.7 ohm,
0.75-1.8 A at 3.3 V. Every continuous limit (L3, L4a, L4b) is exceeded from about 1.0-1.9 V upward. The real current is set by the partner's
source impedance (section 2).

K0b (B1 known answer, SIM): case (c), 27 C, N = 8 against 8 x K0(27 C) at the same junction voltage: see "Bench results" at the end (a first comparison
with K0 on a 50 mV grid gave 5.4 %, which is log-interpolation error of the reference; rerun on a 5 mV grid).

## 2. What each real partner does to an unpowered chip (SIM: `out/b2_*`, `b2p_*`, `b2ac_*`, `b2t_*`; `collect_b2s.py`)

DC operating points; each partner drives one pad or a pair through its own source impedance plus 0.7 ohm; ranges are over 0 / 27 / 85 C and N = 4 / 8 / 16.
The spread with N and temperature is small because the partner impedance, not the diode, sets the current.

| Partner (source level, impedance, legs) | (a) floating: supply node | (b) 6 kohm chip load: current / supply node | (b) 1.65 kohm: supply node | (c) supply held: current per leg | (c) total into supply | (c) diode power, pair |
|---|---|---|---|---|---|---|
| USB peer pull-up 3.3 V, 1.5 k, one leg | 2.82 V .. 2.93 V | 332 uA .. 356 uA / 1.99 V .. 2.14 V | 1.29 V .. 1.38 V | 1.63 mA .. 1.75 mA | 1.63 mA .. 1.75 mA | 1.19 mW .. 1.39 mW |
| USB peer pull-up 3.6 V, 1.425 k | 3.12 V .. 3.23 V | 375 uA .. 400 uA / 2.25 V .. 2.40 V | 1.48 V .. 1.58 V | 1.92 mA .. 2.04 mA | 1.92 mA .. 2.04 mA | 1.4 mW .. 1.65 mW |
| USB FS/LS driver high 3.3 V, 36 ohm, one leg | 2.82 V .. 2.93 V | 411 uA .. 442 uA / 2.47 V .. 2.65 V | 2.40 V .. 2.57 V | 60.8 mA .. 67 mA | 60.8 mA .. 67 mA | 56.1 mW .. 64.8 mW |
| USB FS driver 3.6 V, 28 ohm | 3.12 V .. 3.23 V | 461 uA .. 491 uA / 2.77 V .. 2.95 V | 2.70 V .. 2.87 V | 86 mA .. 95.1 mA | 86 mA .. 95.1 mA | 82.3 mW .. 97 mW |
| USB HS level 0.44 V, 45 ohm, one leg | 0.02 V .. 0.09 V | 0.074 nA .. 8.7e+02 nA / 0.00 V .. 0.01 V | 0.00 V .. 0.00 V | 0.074 nA .. 1.02 uA | 0.074 nA .. 1.02 uA | 0.032 nW .. 4.5e+02 nW |
| USB chirp-level 0.8 V, 45 ohm, both legs | 0.38 V .. 0.48 V | 14.3 uA .. 43.7 uA / 0.09 V .. 0.26 V | 0.06 V .. 0.22 V | 163 uA .. 2.38 mA | 325 uA .. 4.75 mA | 258 uW .. 3.28 mW |
| USB D+ shorted to VBUS 5.25 V, 1 ohm | 4.76 V .. 4.87 V | 736 uA .. 766 uA / 4.42 V .. 4.60 V | 4.38 V .. 4.55 V | 1.03 A .. 1.87 A | 1.03 A .. 1.87 A | 3.55 W .. 3.94 W |
| TMDS sink 3.3 V, 50 ohm, both legs | 2.84 V .. 2.95 V | 415 uA .. 446 uA / 2.49 V .. 2.68 V | 2.43 V .. 2.61 V | 44.8 mA .. 48.9 mA | 89.6 mA .. 97.8 mA | 79.8 mW .. 91.8 mW |
| TMDS sink 3.465 V, 45 ohm, both legs | 3.00 V .. 3.12 V | 442 uA .. 473 uA / 2.65 V .. 2.84 V | 2.60 V .. 2.77 V | 52.8 mA .. 57.6 mA | 106 mA .. 115 mA | 95.2 mW .. 110 mW |
| CMOS clock held high 3.3 V, 33 ohm, one leg | 2.82 V .. 2.93 V | 412 uA .. 442 uA / 2.47 V .. 2.65 V | 2.40 V .. 2.57 V | 65.8 mA .. 72.8 mA | 65.8 mA .. 72.8 mA | 61.4 mW .. 71 mW |
| CMOS clock high 3.63 V, 15 ohm | 3.15 V .. 3.26 V | 467 uA .. 497 uA / 2.80 V .. 2.98 V | 2.75 V .. 2.92 V | 149 mA .. 171 mA | 149 mA .. 171 mA | 159 mW .. 191 mW |
| peak of a 1 Vpp clipped sine (0.5 V), 50 ohm | 0.07 V .. 0.12 V | 0.93 nA .. 3.52 uA / 0.00 V .. 0.02 V | 0.00 V .. 0.01 V | 0.93 nA .. 6.79 uA | 0.93 nA .. 6.79 uA | 0.46 nW .. 3.39 uW |
| AC-coupled link peak 0.3 V per leg, 50 ohm, both legs | 0.00 V .. 0.02 V | 0.0004 nA .. 23 nA / 0.00 V .. 0.00 V | 0.00 V .. 0.00 V | 0.0002 nA .. 11 nA | 0.0004 nA .. 23 nA | 0.00012 nW .. 6.9 nW |
| AC-coupled link peak 0.4 V per leg | 0.01 V .. 0.08 V | 0.027 nA .. 5.2e+02 nA / 0.00 V .. 0.00 V | 0.00 V .. 0.00 V | 0.014 nA .. 2.9e+02 nA | 0.027 nA .. 5.7e+02 nA | 0.011 nW .. 2.3e+02 nW |
| AC-coupled link peak 0.6 V per leg | 0.14 V .. 0.27 V | 1.2e+02 nA .. 15.9 uA / 0.00 V .. 0.09 V | 0.00 V .. 0.07 V | 63 nA .. 125 uA | 1.3e+02 nA .. 250 uA | 75 nW .. 149 uW |
| bench source 3.3 V, 50 ohm, both legs (BB / debug) | 2.84 V .. 2.95 V | 415 uA .. 446 uA / 2.49 V .. 2.68 V | 2.43 V .. 2.61 V | 44.8 mA .. 48.9 mA | 89.6 mA .. 97.8 mA | 79.8 mW .. 91.8 mW |
| external LO peak 2.0 V, 50 ohm, one leg (DC equivalent of the peak) | 1.53 V .. 1.65 V | 199 uA .. 229 uA / 1.19 V .. 1.37 V | 1.14 V .. 1.31 V | 20.6 mA .. 24.1 mA | 20.6 mA .. 24.1 mA | 18.7 mW .. 19.7 mW |

Baseline, provider pads that the chip already has (transistor-level provider cells, chip unpowered, 27 C; 85 C within 4 %):

| Provider pad and source | (a) floating: supply node | (b) 6 kohm: current / supply | (c) held: current | (c) power in the cell |
|---|---|---|---|---|
| `bi_t` host pad, FPGA 3.3 V, 25 ohm | 3.01 V | 0.43 mA / 2.60 V | 80 mA (pad at 1.30 V) | 104 mW |
| `bi_t`, 3.465 V, 15 ohm | 3.18 V | 0.46 mA / 2.76 V | 143 mA | 188 mW |
| `bi_t`, 3.3 V behind 1 kohm | 3.01 V | 0.37 mA / 2.25 V | 2.45 mA | 2.1 mW |
| `asig_5p0` ATB pad, 3.63 V, 50 ohm | 3.22 V | 0.48 mA / 2.86 V | 54.5 mA (pad at 0.903 V) | 49 mW |

Cross-check against existing evidence (known answer from another bench): `atb-provider-pad-force.json` tt/27: 54.58 mA, pad 0.9008 V; here 54.53 mA, 0.9035 V.
`powered-host-backfeed.json` quotes 6.8 mA per host pin (81.6 mA for 12 pins) with its FPGA peer model, and "about 2.7 mA with 1 kohm"; here 2.45 mA with 1 kohm, and
80 mA per pin for a stiff 25 ohm driver: the 6.8 mA figure depends on the weak peer model and is not a bound.

Readings:
- **A provider pad back-feeds at least as hard as an option-A pad**: per pin 80 mA (25 ohm source) against 45-73 mA for the option-A diode behind 33-50 ohm, and it lifts a floating
  supply to pad - 0.29 V against pad - 0.41..0.49 V. Option A adds nothing qualitatively new to the chip; it adds 21 more pads (USB 2, WIRE_TX 2, WIRE_RX 2, REF 2, AUX 2,
  RF_RX 2, RF_TX 2, BB 4, WTX_EXT 2, WMON 1) to the 12 host + 2 ATB + strap + observe pads that already do it, and those new pads face partners the board cannot gate with a bus switch.
- **AC-coupled small-swing links (DisplayPort <= 0.6 V single-ended pp, SATA <= 0.35 V, PCIe <= 0.6 V, XAUI <= 0.8 V, 100BASE-TX secondary +-0.5 V, clipped-sine clock 1 Vpp)**:
  peaks of 0.3-0.5 V: <= 7 uA into a held supply even at 85 C / N = 16, <= 0.12 V on a floating supply. Harmless. (Peaks read from the standards' transmitter limits; EST, not simulated as waveforms.)
- **Anything that holds a pad at a 3.3 V logic or termination level** (TMDS sink, a 100BASE-TX centre-tap rail per B39 if it is powered separately, a CMOS clock, a USB peer's pull-up or driver, a bench source):
  a floating or chip-loaded supply goes to 2.0-3.2 V; a held supply takes 45-171 mA per leg.
- **AC coupling does not stop a large-swing source** (SIM, `b2ac_cmos3v3_*`: 25 MHz 3.3 V CMOS clock, 33 ohm, 1 nF coupling, N = 8, 27 C): the up- and down-diode form a voltage doubler.
  Supply held: 10.6 mA average into the supply, pad swinging -0.91..+0.90 V. Supply floating (2 nF stand-in for the 8 uF so the bench settles): 2.01 V after 40 us and still rising at 3 uA
  (doubler end value Vpp - 2 Vd about 2.0-2.3 V). With 6 kohm: 1.72 V, 0.29 mA. The same holds for the external LO (B3): a 4 Vpp sine from 50 ohm (`b2ac_lo4vpp_*`, run at 25 MHz with 1 nF as a stand-in for 2.45 GHz / 10 pF) gives 5.2 mA average into a held supply and 2.02 V / 0.34 mA with 6 kohm; the floating case did not run.
- **USB**: an unpowered device port sees only the host's 15 kohm pull-downs: no back-feed. With the chip as host or on a hub-like fixture, a self-powered peer's 1.5 kohm pull-up lifts a
  floating supply to 2.8-3.2 V and a chip-loaded one to 1.3-2.4 V at 0.33-0.40 mA. A D+/D- short to VBUS (5.25 V) puts 4.4-4.9 V on a floating or chip-loaded supply (L5 fail: every 3.3 V
  device on the die sees it) and 1.0-1.9 A into a held supply (L4a fail). This holds with the chip powered too: 5.25 V - 3.3 V = 1.95 V across the diode and 1 ohm.

Charging of the 8 uF (SIM, `out/b2t_*`, N = 8, 27 C, source stepped on at t = 0, 22 provider cells on the node; no bond inductance):

| Partner | Initial dV/dt on the supply | 0.5 V | 1.0 V | 1.5 V | 2.0 V | 2.5 V | Value at the end of the run, floating / 6 kohm |
|---|---|---|---|---|---|---|---|
| TMDS sink, 2 x 50 ohm to 3.3 V | 0.0117 V/us | 49 us | 0.11 ms | 0.20 ms | 0.35 ms | 1.05 ms (1.16 ms with 6 kohm) | 2.66 / 2.55 V at 20 ms |
| CMOS clock high, 33 ohm, 3.3 V | 0.0086 V/us | 65 us | 0.15 ms | 0.27 ms | 0.48 ms | 1.5 ms (1.8 ms) | 2.62 / 2.53 V at 10 ms |
| USB FS driver high, 36 ohm, 3.3 V | 0.0080 V/us | 71 us | 0.16 ms | 0.29 ms | 0.52 ms | 1.6 ms (1.95 ms) | 2.62 / 2.53 V at 10 ms |
| USB peer pull-up, 1.5 kohm, 3.3 V | 0.00021 V/us | 2.7 ms | 6.1 ms (6.6 ms) | 10.9 ms (13.1 ms) | 18.7 ms (38.8 ms) | 42 ms (never) | 2.72 / 2.04 V at 400 ms |
| USB pad shorted to VBUS, 5.25 V, 1 ohm | 0.186 V/us | 3.4 us | 6.6 us | 10.3 us | 14.7 us | 20.3 us; 3.63 V after 42 us | 4.53 / 4.48 V at 2 ms |

Known answer: TMDS initial slope by hand 2 x (3.3 - 0.85 V) / 50.7 ohm / 8 uF = 0.0121 V/us (SIM 0.0117). The node reaches the POR-relevant 1.0-1.5 V in 0.1-0.3 ms from any
30-50 ohm partner and in 6-13 ms from a 1.5 kohm pull-up; the last few hundred mV toward the DC values of the table above take seconds (diode current falling exponentially).

## 3. Consequences

### 3a. POR and the state of the digital macro (SIM, `out/b3a_*`; schematic POR deck of the always-on audit, tt/27 unless stated)

Supply waveform: 0 -> plateau in 1 ms, plateau held 200 ms (the back-fed level), then plateau -> 3.3 V in 1 ms (the real supply arrives).
Known answer: cold start 0 -> 3.3 V in 1 ms releases at 39.55 ms (audit `kn_tt_27_3.3_1ms`: 39.55 ms; first attempt failed at the initial time point until the
audit's `.spiceinit` (`ngbehavior=hsa`) was placed in the run directory; a B1 spot check with and without it differs by < 0.1 % in current and < 0.5 mV).

| Back-fed plateau | `porb` during the plateau | Reset after the real ramp | Verdict against L1 |
|---|---|---|---|
| none (cold start) | - | low, released 38.5 ms after the ramp | reference |
| 0.5 V, tt/27 | 0 (hold-off capacitor at 0.04 V) | low, released 38 ms after the ramp | pass |
| 0.5 V, ff/85 | = VDD (POR already "released" at 0.5 V) | low, released 26 ms after the ramp | reset issued, shortened |
| 1.0 V, tt/27 | = VDD (released during the plateau) | low, released 20 ms after the ramp | reset issued, half length |
| 1.0 V, ss/0 | 0 | low, released 43 ms after the ramp | pass |
| 1.5 V, tt/27 | = VDD | **never low: no reset** | fail |
| 2.6 V, tt/27 | = VDD (released 32 ms into the plateau) | **never low: no reset** | fail |

- The declared limit holds: a supply back-fed to >= 1.5 V defeats the POR completely at tt (no pulse when the real supply arrives); at 1.0 V the pulse still comes but shortened; <= 0.5 V is clean.
  Every "holds a pad at a logic level" partner of section 2 puts a floating or chip-loaded supply at 2.0-3.2 V, i.e. in the fail region, within 0.2 ms (30-50 ohm sources) to 11-13 ms (1.5 kohm).
- During the plateau `por_n` = VDD, so `rst_n = reset_n_pad & (por_n | por_bypass)` is released unless RESET_N is low. The macro (5 V-device cells, not functional near 1 V, marginal at 2-2.7 V)
  then runs out of reset at an undefined under-voltage, with all register defaults unreliable; island enables are register bits. Only RESET_N (board supervisor B1 + B49) holds it. A supervisor
  with its threshold inside the supply window does hold RESET_N low for a 2.0-3.0 V back-fed rail (its own minimum operating voltage is typically about 1 V: READ, part not chosen).
- This is not new: the 12 provider host pads and the ATB pads do exactly this today (baseline table), which is why B1, B6, B26 and B49 exist. Option A makes the same thing reachable from
  21 more pads, among them pads whose partners are someone else's equipment (USB peer, TMDS sink).
- Not simulated: ss/ff at 1.5 V, plateaus other than 200 ms, the extracted POR, the macro itself at under-voltage.

### 3b. Do the supply-pad RC clamps fire when a partner connects with a fast edge? (SIM, `out/b3b_*`, tt/27, N = 16 as the stiffest diode)

Die rail = 22 provider cells + 1 nF behind the bond loop (22.5 mohm, 2.2 nH) to the eight 1 uF capacitors; board side otherwise open (regulator off, high impedance).
Partner edge 0 -> level in 0.2 ns through its impedance, 2.3 nH signal bond, 0.7 ohm, 1 pF. "Fired" = clamp gate node above 0.7 V.

| Case | Die rail at 1.5 us | Average slope | Die rail peak in the run | Clamp gate peak | Fired? |
|---|---|---|---|---|---|
| NEGATIVE CONTROL: TMDS sink 2 x 50 ohm, 3.3 V, 8 uF removed | 0.66 V (held by the clamps) | > 10 V/us at the start | 1.90 V | 0.95 V | **yes** (control behaves as required) |
| TMDS sink 2 x 50 ohm, 3.3 V | 0.020 V | 0.012 V/us | 0.11 V in 8 us | 0.031 V | no |
| CMOS driver 15 ohm, 3.63 V | 0.035 V | 0.021 V/us | 0.20 V in 8 us | 0.053 V | no |
| USB pad shorted to VBUS, 1 ohm, 5.25 V | 0.38 V | 0.25 V/us | 2.88 V in 20 us (still rising) | 0.35 V | no, with half the gate margin gone |
| VBUS short, 8 uF removed (second control) | 1.12 V | - | 3.47 V | 1.31 V | yes |

- The eight 1 uF capacitors make firing impossible for every real partner: slope = I / 8 uF, and 0.3 V/us needs 2.4 A. Partners with >= 15 ohm give <= 0.021 V/us, 14-25x below the board rule and 43-75x below the
  lowest firing slew. Only the VBUS short (2.0-2.2 A peak in one signal bond and in the supply bonds) comes close: 0.25 V/us at tt/27 against the 0.3 V/us rule. Worse corners (sf/85 with slow RC) not run.
- The instantaneous dV/dt of the die rail is 330-990 V/us in these runs. That is millivolt-level ringing of the 1 nF die capacitance against the bond inductance in the first nanoseconds
  (rail peak <= 0.2 V in the 15-50 ohm cases) and does not move the clamp timer; the declared L2 has to be read as the slope over the timer constant (1-2 us), which is how it is tabulated here.
- A fired ring clamp with a 25 ohm partner would only hold the rail near 0.7 V for a few microseconds (control case): no energy to speak of. Firing matters for a stiff supply, not for a signal partner.

### 3c. Latch-up (EST; the PDK has no parasitic-bipolar or SCR model, nothing here is simulated)

| Situation | Injected current per pad (from section 2) | Against the +-100 mA test level | Comment |
|---|---|---|---|
| Chip off, supply held at 0 V | TMDS 45-58 mA, USB FS driver 61-95 mA, CMOS 66-73 mA (149-171 mA from a 15 ohm 3.63 V driver), VBUS short 1.0-1.9 A | below, except the stiff CMOS driver and the VBUS short | no supply exists that could sustain a latched path; the p+/n-well diode is a vertical PNP, so a share of this current goes into the substrate under the pad row |
| Chip off, supply floating or chip-loaded | <= 2.8 mA | far below | the supply itself is being raised by the pad (section 3a) |
| Supply ramping up while the partner still drives (B26 violated) | (Vpad - Vdd - 0.85 V) / Rs: TMDS 9 mA per leg at Vdd = 2.0 V, 0 above about 2.6 V | below | the only case where injection and a strong supply coincide; it ends by itself once the supply passes pad - 0.6 V |
| Chip powered, partner level above the die supply | TMDS sink at 3.465 V on a 3.15 V die: 0.33 V forward: 6 pA per finger at 27 C, 2.4 nA at 85 C (K0 at 27 / 85 C) | negligible | a fast die trimmed below 3.15 V against a 3.3-3.6 V logic level would see 0.3-0.6 V forward: up to 0.18 uA per finger at 27 C and 9.5 uA at 85 C |
| Chip powered, RF_TX | pad peaks about 0.8 V above the supply every RF cycle (README section 3 / `rftx_shunt.py`: rest 3.3 V, peak 4.1 V): 0.26 mA per finger at 27 C at the peak (2.3 mA at 85 C), 1.0-4.2 mA for N = 4-16 at 27 C | below the level, but it is a functional failure | the up-diode clips the PA swing and injects at 2.4 GHz |
| Chip powered, USB pad shorted to VBUS | 1-1.9 A | 10-19x above | also lifts the supply (section 2) |

Guard-ring facts (READ, `lu.json` of hspad / wirepad / steering buffer): no n-diffusion farther than 15 um from a p-tap, every p-diffusion inside a closed n+ ring. That is the DRM rule set the provider
pads are also built to; it is a rule audit, not a latch-up measurement, and a pad-site diode cell does not exist yet, so nothing is known about its rings. The pad-site p+ diode must sit in its own n-well with an
n+ ring tied to the supply and a p+ ring to ring VSS (the `diode_pd2nw_06v0` primitive has the SUB ring at 1.87 um), as the provider `asig_5p0` cell does. With that, the injected currents of real partners are at or
below the standard test level; exceeding it takes a driver stiffer than about 25 ohm at 3.63 V or the VBUS short.

### 3d. Continuous current limits (section 2 numbers against L4a, L4b)

| Partner, supply state | Per-leg current | Bond wire 0.34 A | Diode fingers, 3.5 mA each as drawn in the TLP site (14 / 28 / 56 mA for N = 4 / 8 / 16) |
|---|---|---|---|
| any partner, supply floating or chip-loaded | <= 2.8 mA | pass | pass |
| USB peer pull-up, supply held | 1.6-2.0 mA | pass | pass |
| TMDS sink, supply held | 45-58 mA | pass | **fail for N = 4 and 8; N = 16 is at the limit (57.6 mA worst against 56 mA)** |
| USB FS driver high, supply held | 61-95 mA (static high; signalling averages about half) | pass | fail for every N static; N = 16 passes at 50 % duty nominal only |
| CMOS clock, supply held | 66-73 mA high level, 33-37 mA average at 50 % duty (149-171 mA from 15 ohm) | pass | fail for N = 4, 8; N = 16 passes the nominal 50 % duty case only |
| AC-coupled 3.3 V clock / 4 Vpp LO, supply held | 10.6 / 5.2 mA average (SIM) | pass | pass |
| VBUS short, supply held | 1.0-1.9 A | **fail (3-5.5x)** | fail |
| Provider host pad (baseline), supply held | 80-143 mA | pass | provider cell, not ours |

The finger limit is the 6 single Via1 cuts of the supply terminal in `tlp_site.py`; a pad-site cell with a wider terminal (2 cut columns, 12 cuts) doubles it. The limit is an 85 C electromigration (lifetime) number:
it bounds how long a back-fed state may persist, it is not an instant-damage level.
Holding the supply at 0 V (the sinking regulator) is what turns a harmless 0.4-2.8 mA into 45-170 mA: it protects the POR and the macro (3a) at the price of the diode and of the partner.

## 4. Containment, per interface

What each measure can and cannot do (numbers from sections 1-3):

| Measure | Effect | Cost / limit |
|---|---|---|
| Chip load alone | none: 0.07-1.8 mA taken, supply still at pad - 0.65..0.85 V | - |
| Supply bleed resistor Rb, always connected | supply = (Vs - Vd) x Rb / (Rs + Rb); < 0.5 V needs Rb < Rs / 4.4 for a 3.3 V partner: 11 ohm for a 50 ohm partner, 340 ohm for a 1.5 kohm pull-up | 11 ohm burns 0.3 A when powered: not usable; 340 ohm costs 10 mA |
| Regulator that sinks, or active output discharge when disabled (typically 50-300 ohm: READ, part not chosen) | true sink: supply < 0.01 V at 100 mA (case c). A 100 ohm discharge holds < 0.5 V only for partners above 440 ohm (USB pull-up: 0.17 V), not for 50 ohm partners (1.6 V) | turns the back-feed into 45-170 mA continuous per leg through the diode (3d) and out of the partner; regulator must sink >= 0.2 A per driven pair |
| Series resistor at the pad | limits the current: with a held supply 195 ohm keeps N = 4 inside 14 mA at 3.63 V, 49 ohm does it for N = 16. It does NOT by itself keep the supply down: with a 6 kohm chip load < 0.5 V needs 27 kohm; with a 100 ohm discharge 440 ohm | RC with 1.2-3.4 pF pad: 440 ohm gives 0.5-1.5 ns (110-300 MHz): acceptable for a 25-100 MHz CMOS reference (edge slows to about 1-3 ns, more jitter sensitivity) and for baseband test injection; not possible on USB (28-44 ohm total FS, 45 ohm HS), TMDS / multi-Gb/s (50 ohm termination), 2.4 GHz LO or RF |
| Sequencing rule (board: supply up and RESET_N released before any partner drives, B26; host pads behind a bus switch, B6; ATB force only when powered, B7) | complete, where the board owns the partner | cannot be enforced on a USB peer or an HDMI / DVI sink at the other end of a cable |
| Existing behaviour of the provider pads | the die already tolerates the same event on 12 host pads + 2 ATB pads (80 mA per pin from 25 ohm, supply to pad - 0.29 V); B1 / B6 / B7 / B26 / B49 already exist for it | those partners are all board-owned |

Per interface:

| Interface (pads) | Partner with the chip off | Back-feed with option A | Verdict for option A |
|---|---|---|---|
| WIRE_RX (2) | DP / SATA / PCIe / XAUI sources AC-coupled, <= 0.4 V peak per leg; Ethernet transformer secondary +-0.5 V; TMDS source only sinks current | <= 7 uA, supply <= 0.12 V | **acceptable as is.** Rule to add: the 100BASE-TX RX centre-tap divider (B38) is fed from the die supply, not from another rail |
| RF_RX (2) | antenna, AC-coupled | none (signal peaks far below a diode drop) | **acceptable as is** (N = 4 for capacitance) |
| REF_IN, AUX_CLK (4) | oscillator module, LVCMOS 3.3 V or clipped sine; external LO 3-4 Vpp AC-coupled; forwarded / TMDS clock | clipped sine 1 Vpp: <= 7 uA. CMOS 3.3 V: supply to 2.5-3.2 V DC-coupled, about 2.0 V AC-coupled (doubler), or 10-73 mA into a held supply. LO: 5 mA / about 2 V | **acceptable with rule**: B26 as written (source gated on power-good), plus: the reference oscillator and any clock level shifter are powered from the die supply rail, or the clock is a <= 1 Vpp AC-coupled sine. A 440 ohm series resistor on a CMOS reference is a possible second barrier |
| BB_I/Q (4), WTX_EXT (2), WMON (1) | bench instruments; WTX_EXT 0.3-0.8 Vpp AC-coupled from the FPGA | 50 ohm source at 3.3 V: 45-49 mA per pad or supply to 2.5-3.0 V; WTX_EXT data: nothing | **acceptable with rule**: the B7 wording extended to these pads (drive only while powered, or source limited to 1 mA); already implied by B26 |
| USB (2) | device role: host 15 kohm pull-downs only: nothing. Host role / self-powered peer: 1.5 kohm to 3.0-3.6 V. Fault: short to VBUS | peer pull-up: supply to 1.3-3.2 V, 0.3-2 mA: POR defeated (3a) unless the regulator discharges (100 ohm: 0.17 V). VBUS short: supply to 4.4-4.9 V or 1-1.9 A, powered or not | **not acceptable** if short-to-VBUS survival (USB 2.0 7.1.1) is kept as a requirement: no series element is allowed on a 45 ohm HS port and the fault over-volts the whole die. Acceptable only with that requirement waived and device-only use |
| WIRE_TX (2) | TMDS sink (someone else's monitor): 50 ohm to 3.3 V per leg, cannot be sequenced; 100BASE-TX centre-tap rail (B39, board-owned); AC-coupled peers: nothing | 90-115 mA into a held supply (diode fingers over their limit for N <= 8), or supply to 2.4-3.1 V: POR defeated, macro undefined, for as long as the cable is in | **not acceptable** for the TMDS configuration; acceptable with rule B26 only on carriers that never face a DC-coupled sink |
| RF_TX (2) | board chokes to the die supply (no partner) | none when off; **when on, the pad swings about 0.8 V above the supply and the up-diode conducts every cycle** | **not acceptable**, for a functional reason independent of back-feed (a two-diode stack to the supply would be needed: twice the resistance) |
| Host link, ATB, strap, observe (provider) | FPGA 3.3 V | baseline | unchanged; B6 / B7 stay |

Pads that should NOT get up-diodes to the ring supply: **RF_TX_P/N, USB_DP/DN, WIRE_TX_P/N** (6 pads). They take the hybrid of section 5. All other custom pads (15) can take option A with the rules above,
which the board document already carries except for the two additions marked.

## 5. Hybrid: down-diodes to ring VSS at the pad, up path to an isolated rail (no back-feed)

Negative zaps (pad below VSS) are solved in the pad site in every variant (the `pad_tlp_flat` pattern, 0.44 ohm). The question is the positive zap.

### 5.1 Device drops at ESD current (SIM, DC, model only: `out/b5_diode`, `out/b5_nmos_*`)

| | 0.34 A | 0.67 A (1 kV) | 1.0 A | 1.33 A (2 kV) |
|---|---|---|---|---|
| Up-diode (or down-diode, within 10 mV), N = 4 | 1.71 V | 2.46 V | 3.21 V | 3.95 V |
| N = 8 | 1.31 V | 1.70 V | 2.08 V | 2.45 V |
| N = 16 | 1.10 V | 1.31 V | 1.50 V | 1.69 V |

The slope is the model's 8.9 ohm / N series resistance: N = 4 alone spends half of the 8.0 V at 2 kV. This number is exactly what the TLP site is there to calibrate.

Clamp NMOS (`nfet_06v0`, L = 0.7 um), voltage needed for the current, gate at the drain ("full drive": RC-timer + inverter trigger, provider style) / gate at 0.6 x drain (gate-coupled, the coupling ratio of the
existing `rftx_shunt` unit is taken as 0.6: EST from 32 pF against about 19 pF of gate):

| Width | tt/27: 0.67 A | tt/27: 1.33 A | ss/85: 0.67 A | ss/85: 1.33 A |
|---|---|---|---|---|
| 4 mm | 2.78 / 4.55 V | 4.15 / 6.46 V | 3.33 / 5.41 V | 5.03 / 7.34 V |
| 8 mm | 2.01 / 3.28 V | 2.77 / 4.53 V | 2.37 / 3.88 V | 3.31 / 5.39 V |
| 12 mm (the existing unit) | 1.71 / 2.79 V | 2.27 / 3.72 V | 2.00 / 3.28 V | 2.70 / 4.41 V |

Known answer: 4 mm with gate = drain = 3.3 V at tt/27 gives 0.915 A (CLAMP.md stage A, one provider cell: 0.92 A). Negative control: gate grounded, 0.3 nA at 8 V (tt), 0.34 uA (ff/85): cannot carry 1.33 A, as required.

### 5.2 Resistance budget for 8.0 V at the bond pad

Budget = (8.0 V - V_diode(N) - V_clamp) / I, for ALL metal in the loop (bond pad to diode, diode to clamp, clamp to ring VSS), ohm:

| Clamp | 2 kV, tt/27: N = 4 / 8 / 16 | 2 kV, ss/85 | 1 kV, tt/27 | 1 kV, ss/85 |
|---|---|---|---|---|
| 4 mm full drive | none / 1.06 / 1.63 | none / 0.39 / 0.96 | 4.1 / 5.3 / 5.8 | 3.3 / 4.4 / 5.0 |
| 8 mm full drive | 0.96 / 2.09 / 2.66 | 0.55 / 1.68 / 2.25 | 5.3 / 6.4 / 7.0 | 4.7 / 5.9 / 6.5 |
| 12 mm full drive | 1.34 / 2.47 / 3.04 | 1.02 / 2.15 / 2.72 | 5.7 / 6.9 / 7.4 | 5.3 / 6.4 / 7.0 |
| 12 mm gate-coupled (today's core clamp) | 0.25 / 1.38 / 1.95 | none / 0.85 / 1.42 | 4.1 / 5.2 / 5.8 | 3.4 / 4.5 / 5.1 |

Variant "up path to the isolated rail in the core" (ESD-METAL V2): the Metal2 neck of 4-8 ohm is inside this loop.
- 2 kV: the neck alone drops 5.3-10.6 V at 1.33 A. The budget for everything is 0.25-1.95 ohm with today's clamp. **Not feasible** unless the neck comes down to about 0.5-1 ohm (the 0.3-0.9 pF per pad of ESD-METAL section 4).
- 1 kV: budget 3.4-5.8 ohm with today's gate-coupled clamp. A 4.0 ohm neck plus the best measured remainder (`pad_hspad` f6: rail to clamp 0.5-0.8 ohm, return 2.1-3.1 ohm; the pad-side diode feed moves to the core side of the
  neck) is 6.6-7.9 ohm: **misses at 1 kV as well**, by 1-4 ohm; this agrees with the 6.8-7.3 V + 2.3 V that ESD-METAL reports for the improved `pad_hspad`. It would close at 1 kV with N >= 8 and a neck of about 2 ohm.

### 5.3 Local clamp inside the pad site (SIM, HBM transient with transistor-level provider `dvdd` cells as the local clamp: `out/b5h_*`)

HBM source 100 pF / 1.5 kohm / 7.5 uH; bond pad -> 0.44 ohm -> up-diode -> 0.3 ohm -> local rail -> k provider clamp cells (4 mm NMOS each, own RC trigger) -> VSS.
The source delivers 1.22 A peak at "2 kV" and 0.61 A at "1 kV" in this deck (the README's 1.33 / 0.67 A are the ideal 1.5 kohm values); add about 0.3-0.4 V for 1.33 A.

| Case | Bond-pad peak | Local-rail peak | Limit 8.0 V |
|---|---|---|---|
| 2 kV, N = 16, 4 mm (k = 1), tt/27 | 6.44 V | 5.13 V | pass, 1.6 V margin |
| 2 kV, N = 16, 8 mm (k = 2), tt/27 | 5.49 V | 4.38 V | pass |
| 2 kV, N = 16, 8 mm, ss/0 | 6.33 V | 5.16 V | pass |
| 2 kV, N = 16, 8 mm, ss/85 | 6.49 V | 5.38 V | pass, 1.5 V margin |
| 2 kV, N = 16, 12 mm (k = 3), tt/27 | 5.17 V | 4.04 V | pass |
| 2 kV, N = 8, 8 mm, tt/27 | 5.87 V | 4.37 V | pass |
| 1 kV, N = 16, 4 / 8 / 12 mm, tt/27 | 5.38 / 4.84 / 4.60 V | 4.38 / 3.82 / 3.56 V | pass |
| NEGATIVE CONTROL: 2 kV, 8 mm, timer capacitor removed | 13.2 V | 11.8 V | **fail**, as required |

- A local clamp of **8 mm with N = 16 holds the bond pad at 5.5-6.5 V at 2 kV across tt and ss (0 and 85 C)** with 0.74 ohm of metal in the loop; from 5.2 the loop may hold up to about 2.2 ohm at ss/85.
  4 mm is enough at tt (6.4 V) and by the DC table marginal at ss (budget 0.96 ohm at 1.33 A): a 1 kV solution with margin, not a 2 kV one.
- The local rail peaks at 5.1-5.4 V at ss: inside the 6.0 V screen of 6 V devices. Anything 3.3 V on the pad net still needs its secondary stage behind the neck (the neck then helps: it is the series resistor).
- Model limits: no snapback, no self-heating, no gate-oxide or junction breakdown in the `nfet_06v0` model at 5-6.5 V drain with 2.6-3.9 V on the gate; the provider trigger only lifts the gate to 2.7-3.9 V in the event
  because it is powered from the rail it clamps. These are surrogate numbers of the same kind as every other HBM figure in the pads README.
- An RC-triggered local clamp fires on the first fast pad edge after its rail has discharged (the rail then sits at pad peak - Vd and only leaks away): the same first-edge behaviour the isolated rail has today.
  A gate-coupled version needs the 32 pF coupling capacitor, which is a 16,200 um2 MIM today and cannot exist under the ring rails (Metal1 / Metal2 only); as a MOS capacitor it would be about 14,000 um2. So the in-site clamp
  has to be the RC-timer + inverter kind (provider trigger: 2,000 um2 MOS capacitor + 360 kohm poly).

Does it fit a 75 x 280 um site (21,000 um2) under the ring rails? (EST from existing layouts: `rail_shunt_v2` bank 12.0 mm in 293 x 60 um = 0.68 mm of gate width per 1,000 um2 including its tap columns;
`pad_tlp_flat` 4 + 4 fingers with bars about 61 x 31.5 um; provider trigger.)

| Item | Area (um2) |
|---|---|
| Diodes 16 up + 16 down with bars | about 7,700 (4 x the TLP-site block); 8 + 8: about 3,850 |
| Clamp NMOS 8 mm / 4 mm | about 11,700 / 5,900 (75 um wide rows of about 2.7 mm per 60 um of depth: 3 rows / 1.5 rows) |
| RC trigger (MOS capacitor, 12 poly resistors, 3 inverters) | about 4,000 |
| Signal riser through the site (Metal2, 8 um wide + spacing, 280 um) | about 3,400 of Metal2 track, over devices only where Metal1 suffices |

| Configuration | Total | Of the available area | Fits? |
|---|---|---|---|
| One site, N = 16, 8 mm | 23,400 + riser | 111 % of 21,000 | **no** |
| One site, N = 16, 4 mm | 17,600 + riser | 84 % | yes, tight; 1 kV-class margin only |
| One site, N = 8, 8 mm | 19,550 + riser | 93 % | marginal |
| Two sites of a differential pair sharing one 8 mm clamp and trigger, N = 16 per pad | 31,100 + 2 risers | 74 % of 42,000 | **yes** |
| Same, N = 8 per pad | 23,400 + 2 risers | 56 % | yes |

So a pair-shared 8 mm local clamp fits; a single pad (WMON) gets 4 mm. All six pads singled out in section 4 are pairs (RF_TX, USB, WIRE_TX). Metal: the clamp current runs on Metal1 + Metal2 only;
a 75 um wide Metal2 plate over 150 um is 0.18 ohm (0.09 ohm with Metal1 in parallel), and the VSS side can go up to ring DVSS on Metal3 only inside the DVSS band (depth 70-117 um). Inside the 0.96-2.25 ohm budget, but it is
the item a layout has to prove with resistance extraction. Not done: any layout, DRC, the 6 V-device latch-up rule (15 um to a tap) under the rails, CDM.

## 6. Bench results against the declared acceptance

| Bench | Known answer | Negative control |
|---|---|---|
| K0 | 0.1 % worst (limit 3 %) | passed: equation without the knee term is off by up to 38 % |
| B1 | (c) vs 8 x K0(27 C, 5 mV grid) at the same junction voltage: 0.05 % worst | passed: no diode -> 7 fA, 1e-15 V |
| B2 (added cross-checks) | ATB provider pad 54.53 mA / 0.9035 V against 54.58 mA / 0.9008 V on record; TMDS charging slope 0.0117 against 0.0121 V/us by hand | - |
| B3b | no 8 uF: clamps fire (gate 0.95 V and 1.31 V) | is the known answer |
| B3a | cold start 39.55 ms against 39.55 ms | cold start shows a reset; 1.5 V and 2.6 V plateaus show none |
| B5 | 4 mm NMOS 0.915 A at 3.3 V against 0.92 A | passed: gate grounded 0.3 nA at 8 V; HBM with the timer capacitor removed 13.2 V |

Deviations from the plan, stated: (1) L2 was declared as an instantaneous dV/dt; the runs show 330-990 V/us of millivolt-level ringing, so the verdict uses the slope over 1.5 us and the clamp gate voltage.
The limit value was not changed. (2) The first B1 known-answer comparison gave 5.4 % because the reference was interpolated on a 50 mV grid; the reference was rerun on 5 mV and the comparison is 0.05 %.
(3) B1, B2, B2t, B5 and the CMOS B2ac runs were made before the `.spiceinit` (`ngbehavior=hsa`) was in the run directory; B1 was spot-checked with it (< 0.1 %), the others were not rerun. B3a, B3b and the LO runs have it.

## 7. Simulated, estimated, read, not done

- **Simulated here** (ngspice, pinned container, PDK models, one job at a time): K0; B1 (45 DC sweeps); B2 (17 partners x 5 supply states x 9 T/N); provider `bi_t` / `asig_5p0` baseline (27 and 85 C);
  8 uF charging for 5 partners; AC-coupled 3.3 V clock (3 supply states) and 4 Vpp sine (held, 6 kohm); POR with back-fed plateaus (7 runs); partner edges into the ring behind the bond loop (3 cases + 2 controls);
  diode and clamp DC at ESD current; HBM into a local clamp (9 cases + control).
- **Estimated**: latch-up (all of 3c); signal levels of the AC-coupled standards; the cost of series resistors; the 0.6 coupling ratio of the existing gate-coupled unit; every area number in 5.3; the regulator discharge figures.
- **Read, not rerun**: clamp firing thresholds (CLAMP.md), POR dip behaviour (core_support README), always-on currents (always-on-audit section 6), metal resistances (ESD-METAL.md), guard-ring audit (`lu.json`), board rules.
- **Not done**: the unpowered chip as a real netlist (the load is a resistor at three values; the digital macro and the islands at 1-3 V are not simulated); the substrate share of the diode current (two-terminal model);
  any corner other than typical for the back-feed benches, and only tt (plus one ss, one ff point) for the POR; sf/85 slow-RC clamp corner for the VBUS edge; 2.45 GHz LO rectification (run at 25 MHz with a 1 nF
  coupling capacitor as a stand-in, diode transit time not in the model); the 1 Vpp sine and the floating-supply LO transients (aborted at the initial time point twice, bounded from the DC peak instead);
  HBM with the local clamp at 1.33 A exactly, at ff, or with N = 4; CDM; any layout, extraction or DRC of a pad-site cell; mismatch; the powered case of a pad above the supply beyond the K0 numbers;
  USB VBUS short with the chip powered and a real regulator model.
