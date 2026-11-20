# QVCO r6b on a reduced rail VDD_LO (LO owner, 2026-11-14; `envq.py`, staged real loads, band 15 / VTUNE 0.3 V = weakest tank setting)
Start criterion: oscillates, >= 0.5 V differential peak, |Q-I| = 90 +- 10 deg.
| tank case | die supply | VDD_LO | diff peak V | I(QVCO) mA | tank CM V | result |
|---|---|---|---|---|---|---|
| PF85 (ss/32, L-15 %, Q 4, MIM 5 ohm, varactor Q 8) | 3.15 | 3.15 | 0.736 | 21.6 | 1.36 | PASS |
| PF85 | 3.15 | 2.38 | 0.001 | 8.2 | 1.02 | **FAIL (no start)** |
| PF85 | 3.50 | 2.69 | 0.003 | 13.1 | 1.15 | **FAIL** |
| PF85 | 3.50 | 2.80 | 0.003 | 14.9 | 1.20 | **FAIL** |
| PF85 | 3.50 | 2.95 | 0.117 | 17.5 | 1.27 | **FAIL** |
| PF85 | 3.50 | 3.05 | 0.618 | 19.8 | 1.31 | PASS |
| SS (ss/32, nominal tank) | 3.50 | 2.69 | 1.544 | 17.5 | 1.11 | PASS |
| TT (tt/27, nominal tank) | 3.30 | 2.56 | 1.665 | 19.3 | 1.05 | PASS |
| TT | 3.30 | 2.38 | 1.502 | 16.6 | 0.96 | PASS |
Reading: with a nominal-Q tank the QVCO runs on the regulated rail at every corner tried (current 16.6-19.3 mA: use 20 mA as the regulator load, 25 mA as the bound). With the full-pessimistic tank at ss it needs VDD_LO >= 3.05 V (minimum passing; 2.95 V fails), i.e. no regulator dropout is affordable there: such a die runs with the regulator in bypass (VIN - 0.1 V) on a trimmed supply.

# Top/bottom of range vs removed fixed tank C (2026-11-20, `sens/`, staged loads, C removed per tank node as a negative `fill`)
| removed fF/node | top PF115 b0 vt3.0 route 40 (>= 2.558) | bottom OPT85 b15 vt0.3 route 0 (<= 2.330) |
|---|---|---|
| 0 | 2.532 FAIL | 2.300 PASS |
| 60 | 2.563 PASS (0.2 %) | (interpolated ~2.317) |
| 120 | 2.595 PASS (1.4 %) | 2.334 FAIL |
Window about 60-110 fF per node: removing fixed C alone barely closes both ends. The r8 port tracks (+163 um of Metal4 on each tank net, ASM-1) add C back and are not in these runs. Fix needs fixed-C removal (lo_ext input / route) AND a larger band step.
