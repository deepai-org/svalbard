# Full-coverage resistance audit: wired-TX cells (GF180MCU)

The thresholds were written to `THRESHOLDS.md` before any result was read. The amendments at the end of that file changed the
method only, not the threshold values. Machine-readable output is in `rcov.json`: per cell it has coverage, the failing nets,
the negative control and every audited net. Nothing outside this directory was changed.

## Method
* **Extraction.** `ext.py` runs one Magic extresist job per cell. It uses the analog image `tools.ANALOG_IMAGE` (the canary
  image's Magic is recorded as crashing in extresist), `--cpus 1`, `OMP_NUM_THREADS=1`, and the repo recipe (`extract_rc` /
  s13 `rc.py`) with two changes: **`extresist tolerance 0` and `extresist simplify off`**. VDD, VSS and VSUBS are not
  resisted. The GDS files come from `generated/fast/`. Each run took 1 to 10 s.
* **R_series (`audit.py`).** This is computed over each net's extracted resistor graph. For every load (a FET gate, a
  resistor or diode terminal, or a port), take the lowest-R path from the nearest driver (a FET drain or source), then take
  the maximum over all loads. A port-only net uses its port as the driver.
* **Classified R = "wire" R.** The final resistor into each device terminal node (`.tN`) is set to 0. That resistor is
  Magic's poly-gate or diffusion access inside the device, for example ~300 ohm along an 11 um gate finger. It is not
  wiring, and the drawn-R netlists leave it out too. `rcov.json` also reports the R with those stubs included
  (`R_incl_stubs`) and the number of failures under that stricter metric.
* **Ron model.** Ron = K·(L/0.28 um)/W, with K_n = 2.0 kOhm·um and K_p = 4.5 kOhm·um. The driver Ron of a net is the
  minimum over all FETs whose drain or source touches it, which gives the strictest threshold.
* **C_net.** This is max(C from the cell's `.ext.spice`, C of the same net in this extraction). Unnamed flattened nets
  (`a_x_y#`) cannot be matched by name to `.ext.spice`; for about half of all nets the C comes from this extraction.

## Thresholds (from THRESHOLDS.md)
(a) R < 5 % of the driver Ron. (b) R·C < 2 ps. Timing nets (PH*/PS*, clocks, F*/stream, MAIN/POST_P/N, tails, CML
trunks, BM/BQ) pass only on (b). All other nets pass on (a) or (b).

## Coverage
| cell | nets total (non-supply) | in drawn-R netlist | audited | FAIL (wire R) | FAIL if device stubs counted |
|---|---|---|---|---|---|
| wtx_ser8d | 1166 | 113 | 1053 | 32 | 393 |
| wtx_mux8 | 490 | 98 | 392 | 18 | 101 |
| wtx8_aux | 126 | 5 | 121 | 1 | 27 |
| pt_wiredtx8 | 1772 | 101 | 1671 | 140 | 671 |

Extresist resisted 83 % (aux), 52 % (ser8d), 80 % (mux) and 62 % (block) of nets. The rest are single-tile nets, so their
R is about 0. The drawn-R netlist names VDD, VSS and `XH3_1.CK` (ser8d) have no non-supply counterpart in this extraction.

## Negative control: does the extractor reproduce the known drawn R? Result: MIXED
* **PASS (within 7 %), 3 or more nets per cell.** These are nets whose R in `*.rc.spice` comes from Magic's own tolerance-10
  extresist run. In aux: ATB_NBIAS 131.7 vs 140.3 ohm, ATB_PBIAS 120.0 vs 128.6, TAP_EN 288.6 vs 288.6. In ser8d: D0..D39
  and SERQ at a ratio of 1.000, plus XCK.QK0/1, XDV.CK and XL*.MA* at about 1.01. In mux: ENBM, ENBQ, ENP, OVP, OVN and POL
  at 1.00 to 1.03. This is the same tool, so it shows the parser and path metric reproduce Magic. It is not independent.
* **FAIL (outside 30 %).** These are the lumped resistors built by hand in `add_wire_r` and `add_top_r`. Wire R from this
  extraction compared with the drawn R:

  | net | drawn | wire R |
  |---|---|---|
  | XS*.XTM | 2.35 | 29.3 |
  | XS*.ANM | 13.6 | 30.1 |
  | XS*.APQ | 6.1 | 19.3 |
  | BM* | 30.2 | 54.2 |
  | MAIN_P | 0.26 | 5.5 |
  | POST_P | 0.16 | 8.3 |
  | PH* (block) | 5.2 | 52.9 |
  | PS0 | 50.4 | 106 |
  | SERQ (block) | 41.3 | 57.1 |
  | F1 | 6.0 | 46.4 |

  Counting device stubs, the ratios are 4× to 280×.

  The XS0.XTM breakdown (from the kept `.res.ext`) explains the gap. Its pure-metal path is about 3.8 ohm (segments of
  0.25 + 0.49 + 0.54 + 0.49 + 0.78 + 0.78 + 0.49 ohm), against 2.35 drawn, so about 1.6×. The rest is 7 to 26 ohm per hop
  in contact or via stacks and poly-track pieces (`n7–n8` 13.3, `n3–n4` 12.5, `n2–n1` 25.7, `XTM–n10` 7.5). The drawn
  model does not include these, and they come before the gate-finger stubs.
* **Conclusion.** The drawn lumped values cover metal only and under-estimate the real series R of the trunks, buses and
  top-level phase lines by about 2× to 20×. The owner should check this against the drawn-R model. Contacts, vias and
  poly-track access are missing from it.

## Other findings
* **The block netlist does not carry the sub-cells' Magic R.** In `pt_wiredtx8.rc.spice`, nets that are resisted in
  `wtx_mux8.rc.spice` and `wtx_ser8d.rc.spice` have no resistors at all. Examples are XMUX.ENBQ and XMUX.ENBM (about
  1.2 kOhm each, RC about 100 ps), and XSER.XCK.QK0/1, XSER.XDV.LDO and XSER.XCTL.QRST (RC 48 to 69 ps). That is why the
  block has 140 failures compared with 51 in the sub-cells.
* **Most failures are static or slow lines.** These are D*, *_CODE*, enables, bias and ATB lines. The ones that bear on
  timing are listed first in each table below:
  * ser8d PH0..PH315: RC 2.2 to 2.6 ps.
  * register clocks XH*_0/1.CK: up to 6.8 ps in the block.
  * clock-divider nets XP0.XN0..2 / XCK.QKN*, QD and QDN: 2.3 to 3.3 ps.
  * load strobes XL*.LD and LDB: about 2.3 to 2.4 ps.
  * mux per-slice controls UP*/VP*: 3.1 to 3.9 ps.

## Failing nets (wire-R metric). Owner adds R; nothing was modified here

### wtx_ser8d

| net | R wire (ohm) | R incl. device stubs | C (fF) | RC (ps) | driver (Ron) | timing | why it matters |
|---|---|---|---|---|---|---|---|
| XH3_0.CK | 45.6 | 242 | 119.1 | 5.43 | X1600 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| XP0.XN1 | 37.7 | 227 | 87.2 | 3.28 | X1675 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| XH7_1.CK | 45.6 | 242 | 63.3 | 2.89 | X2107 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| XP0.XN0 | 39.6 | 268 | 68.0 | 2.69 | X1296 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| PH135 | 61.0 | 549 | 42.8 | 2.61 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| PH45 | 61.6 | 550 | 41.4 | 2.55 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| XH6_1.CK | 45.6 | 242 | 54.8 | 2.50 | X1842 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| PH0 | 62.1 | 550 | 39.5 | 2.46 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| XL7.LD | 38.4 | 696 | 62.9 | 2.41 | X369 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL6.LD | 38.4 | 696 | 62.7 | 2.41 | X1072 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| PH315 | 60.8 | 549 | 39.6 | 2.40 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| XL3.LD | 38.4 | 696 | 62.6 | 2.40 | X2135 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL2.LD | 38.4 | 696 | 62.4 | 2.40 | X645 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL5.LD | 38.4 | 696 | 62.4 | 2.39 | X149 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL1.LD | 38.4 | 696 | 62.3 | 2.39 | X2253 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL4.LD | 38.4 | 696 | 62.2 | 2.38 | X1067 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL0.LD | 38.4 | 696 | 62.2 | 2.38 | X1227 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XP0.XN2 | 35.7 | 186 | 65.4 | 2.34 | X1184 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| PH225 | 60.5 | 549 | 38.4 | 2.32 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| PH270 | 60.3 | 548 | 38.2 | 2.30 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| XL7.LDB | 38.6 | 607 | 59.1 | 2.28 | X1929 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL6.LDB | 38.6 | 607 | 59.1 | 2.28 | X775 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL5.LDB | 38.6 | 607 | 58.9 | 2.27 | X1705 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL3.LDB | 38.6 | 607 | 58.9 | 2.27 | X1293 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL1.LDB | 38.6 | 607 | 58.8 | 2.27 | X1444 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL2.LDB | 38.6 | 607 | 58.8 | 2.27 | X2375 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL4.LDB | 38.6 | 607 | 58.6 | 2.26 | X153 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XL0.LDB | 38.6 | 607 | 58.6 | 2.26 | X382 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| PH90 | 61.0 | 549 | 36.8 | 2.24 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| PH180 | 60.4 | 548 | 36.5 | 2.20 | port | yes | phase/clock distribution into the serializer: RC adds skew between phases (timing net) |
| XP2.Q | 45.6 | 242 | 45.7 | 2.08 | X1940 nfet_03v3 W=4u L=0.28u (500 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| XH5_1.CK | 45.6 | 242 | 43.9 | 2.00 | X1327 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |

### wtx_mux8

| net | R wire (ohm) | R incl. device stubs | C (fF) | RC (ps) | driver (Ron) | timing | why it matters |
|---|---|---|---|---|---|---|---|
| VP0 | 77.3 | 335 | 50.8 | 3.92 | X940 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| VP5 | 76.9 | 335 | 49.7 | 3.83 | X1536 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP4 | 78.7 | 337 | 48.5 | 3.82 | X411 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP0 | 75.7 | 334 | 50.4 | 3.81 | X1514 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP6 | 78.7 | 337 | 48.1 | 3.79 | X819 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| VP2 | 77.3 | 335 | 48.8 | 3.77 | X512 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| RUN | 80.1 | 339 | 46.6 | 3.74 | X1438 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| VP6 | 76.9 | 335 | 47.8 | 3.68 | X269 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP1 | 75.7 | 334 | 48.0 | 3.63 | X1662 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP2 | 75.7 | 334 | 46.9 | 3.55 | X1642 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| VP4 | 76.9 | 335 | 45.7 | 3.52 | X1518 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| VP3 | 69.5 | 328 | 50.5 | 3.51 | X673 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| VP7 | 69.2 | 327 | 50.5 | 3.49 | X81 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| VP1 | 77.3 | 335 | 43.7 | 3.38 | X1107 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP3 | 67.9 | 326 | 48.8 | 3.31 | X137 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP5 | 78.7 | 337 | 42.1 | 3.31 | X992 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| UP7 | 70.9 | 329 | 44.3 | 3.14 | X839 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| EXT | 61.8 | 292 | 38.0 | 2.35 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |

### wtx8_aux

| net | R wire (ohm) | R incl. device stubs | C (fF) | RC (ps) | driver (Ron) | timing | why it matters |
|---|---|---|---|---|---|---|---|
| ENPOST_G | 55.8 | 238 | 36.4 | 2.03 | X263 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |

### pt_wiredtx8

| net | R wire (ohm) | R incl. device stubs | C (fF) | RC (ps) | driver (Ron) | timing | why it matters |
|---|---|---|---|---|---|---|---|
| XMUX.ENBQ | 1161.7 | 1237 | 95.3 | 110.71 | X4518 nfet_03v3 W=1u L=0.28u (2000 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| XMUX.ENBM | 1151.2 | 1227 | 88.3 | 101.61 | X1325 nfet_03v3 W=1u L=0.28u (2000 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| XSER.XCTL.QRST | 54.5 | 866 | 1262.6 | 68.85 | X3047 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| TAP_EN | 251.6 | 423 | 251.2 | 63.19 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| XSER.XCK.QK0 | 69.0 | 734 | 888.2 | 61.31 | X1414 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XCK.QK1 | 68.8 | 734 | 886.4 | 61.01 | X1889 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XDV.LDO | 71.2 | 775 | 679.2 | 48.37 | X1488 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| POST_CODE7 | 195.0 | 327 | 234.9 | 45.80 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| POST_POL | 220.5 | 360 | 199.4 | 43.96 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| POST_CODE4 | 182.1 | 312 | 229.2 | 41.75 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| POST_CODE5 | 180.4 | 310 | 222.4 | 40.14 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| ATB_NBIAS | 143.5 | 151 | 268.9 | 38.59 | X3862 nfet_03v3 W=4u L=0.28u (500 ohm) | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| ENM | 119.7 | 361 | 318.0 | 38.06 | X3426 nfet_03v3 W=4u L=0.28u (500 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| MAIN_CODE5 | 172.9 | 303 | 218.5 | 37.79 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| ATB_PBIAS | 138.5 | 148 | 256.1 | 35.46 | X2848 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| MAIN_CODE6 | 169.6 | 299 | 201.6 | 34.19 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| POST_CODE6 | 176.6 | 306 | 167.1 | 29.50 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| MAIN_CODE0 | 164.1 | 352 | 165.3 | 27.12 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| TX_RUN | 137.4 | 339 | 180.8 | 24.85 | X2408 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| OVP | 111.0 | 334 | 188.8 | 20.97 | X3369 nfet_03v3 W=4u L=0.28u (500 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| OVN | 111.3 | 315 | 163.1 | 18.16 | X1056 nfet_03v3 W=4u L=0.28u (500 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| D28 | 83.4 | 659 | 171.5 | 14.30 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D20 | 79.9 | 740 | 176.1 | 14.07 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D4 | 81.7 | 683 | 169.9 | 13.87 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D29 | 81.6 | 657 | 168.7 | 13.77 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D21 | 78.1 | 738 | 173.7 | 13.57 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D30 | 81.0 | 656 | 166.8 | 13.51 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D31 | 81.0 | 656 | 165.6 | 13.42 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D5 | 80.1 | 682 | 167.6 | 13.42 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D24 | 77.7 | 653 | 171.1 | 13.30 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D6 | 79.3 | 681 | 166.5 | 13.20 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D14 | 80.7 | 621 | 163.5 | 13.19 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D23 | 77.2 | 737 | 170.4 | 13.15 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D7 | 78.8 | 680 | 165.8 | 13.05 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D15 | 80.2 | 620 | 162.4 | 13.02 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D8 | 77.7 | 618 | 166.8 | 12.96 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| XMUX.ENMI | 112.1 | 372 | 113.0 | 12.66 | X291 nfet_03v3 W=4u L=0.28u (500 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| D25 | 76.0 | 651 | 166.7 | 12.66 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D1 | 74.9 | 676 | 167.1 | 12.52 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D26 | 75.6 | 651 | 165.6 | 12.51 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D17 | 72.5 | 733 | 171.9 | 12.46 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D9 | 75.8 | 616 | 164.1 | 12.44 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D2 | 74.4 | 676 | 166.5 | 12.38 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D18 | 72.1 | 732 | 170.9 | 12.32 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D10 | 75.4 | 616 | 163.1 | 12.30 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D27 | 74.9 | 650 | 163.4 | 12.24 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D3 | 73.7 | 675 | 165.1 | 12.17 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D32 | 72.0 | 791 | 168.7 | 12.14 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| POST_CODE0 | 113.6 | 243 | 106.4 | 12.09 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| D19 | 71.4 | 732 | 168.9 | 12.06 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D11 | 74.8 | 615 | 161.0 | 12.04 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| POST_CODE1 | 112.3 | 242 | 104.4 | 11.72 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| POST_CODE2 | 111.4 | 241 | 104.7 | 11.67 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| D33 | 70.2 | 789 | 165.2 | 11.60 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D34 | 69.8 | 789 | 164.4 | 11.48 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D0 | 76.3 | 678 | 148.2 | 11.30 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D37 | 75.9 | 795 | 145.4 | 11.03 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D36 | 77.6 | 796 | 130.1 | 10.10 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| XSER.XCK.QD | 56.6 | 617 | 174.6 | 9.89 | X1747 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| MAIN_CODE7 | 101.5 | 234 | 96.6 | 9.81 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| DX | 98.8 | 342 | 98.0 | 9.69 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D16 | 74.2 | 734 | 129.6 | 9.62 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D12 | 83.1 | 623 | 114.5 | 9.52 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D22 | 77.7 | 738 | 121.3 | 9.42 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| MAIN_CODE1 | 103.0 | 233 | 91.3 | 9.40 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| D38 | 75.2 | 794 | 124.5 | 9.36 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D13 | 81.5 | 622 | 113.0 | 9.20 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| D35 | 69.2 | 788 | 132.6 | 9.17 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| EXT | 73.1 | 306 | 121.2 | 8.86 | X3949 nfet_03v3 W=4u L=0.28u (500 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| D39 | 75.6 | 794 | 116.7 | 8.82 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| ISLAND_OFF | 104.0 | 286 | 84.3 | 8.77 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| MAIN_CODE3 | 92.8 | 222 | 93.5 | 8.68 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| MAIN_CODE4 | 93.3 | 223 | 90.1 | 8.40 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| MAIN_CODE2 | 92.7 | 222 | 90.2 | 8.36 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| ENMAIN_G | 70.7 | 303 | 117.4 | 8.30 | X3514 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| EN_POST | 90.8 | 259 | 90.3 | 8.19 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| EN_MAIN | 90.4 | 259 | 90.3 | 8.17 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| ENPOST_G | 68.0 | 347 | 117.4 | 7.98 | X3451 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| POST_CODE3 | 102.7 | 232 | 76.9 | 7.90 | port | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| IDLE | 88.0 | 272 | 88.4 | 7.78 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| SER_EN | 89.9 | 259 | 84.8 | 7.63 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| TAP_N | 95.9 | 99 | 76.8 | 7.37 | X4043 nfet_03v3 W=4u L=0.28u (500 ohm) | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| IDLE_MODE | 86.2 | 251 | 84.1 | 7.25 | port | no | static/slow enable or mode line: RC only matters at enable/mode change (low criticality) |
| TAP_P | 94.5 | 97 | 75.9 | 7.17 | X5008 nfet_03v3 W=4u L=0.28u (500 ohm) | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| WTX_EXT | 84.9 | 250 | 82.5 | 7.01 | port | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| WTX_EXT_DATA | 78.7 | 83 | 87.9 | 6.91 | X1965 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | parallel data input (word-rate): large R*C slows the setup into the load latches |
| XSER.XH0_0.CK | 45.6 | 242 | 149.4 | 6.81 | X1185 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| a_51268_56464 | 104.9 | 306 | 60.7 | 6.36 | X3244 nfet_03v3 W=4u L=0.28u (500 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| XSER.XH2_0.CK | 45.6 | 242 | 119.1 | 5.43 | X3434 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XH1_0.CK | 45.6 | 242 | 109.5 | 4.99 | X2047 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| a_55268_53494 | 100.6 | 263 | 49.0 | 4.93 | X1276 nfet_03v3 W=1u L=0.28u (2000 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| a_34918_47454 | 129.9 | 267 | 33.2 | 4.32 | X2461 nfet_03v3 W=1u L=0.28u (2000 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| a_52266_63184 | 74.7 | 348 | 57.2 | 4.27 | X681 nfet_03v3 W=4u L=0.28u (500 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| a_49942_64978 | 87.8 | 366 | 45.9 | 4.03 | X768 nfet_03v3 W=4u L=0.28u (500 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| XMUX.VP0 | 77.3 | 335 | 50.8 | 3.92 | X2735 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.VP5 | 76.9 | 335 | 49.7 | 3.83 | X2474 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.UP4 | 78.7 | 337 | 48.5 | 3.82 | X958 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| a_53440_63184 | 73.2 | 464 | 52.2 | 3.82 | X624 nfet_03v3 W=4u L=0.28u (500 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| XMUX.UP0 | 75.7 | 334 | 50.4 | 3.81 | X5042 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| POST_BIAS | 52.5 | 71 | 72.2 | 3.79 | X1956 pfet_03v3 W=8u L=0.28u (562 ohm) | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| XMUX.UP6 | 78.7 | 337 | 48.1 | 3.79 | X3873 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.VP2 | 77.3 | 335 | 48.8 | 3.77 | X570 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.VP6 | 76.9 | 335 | 47.8 | 3.68 | X943 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.UP1 | 75.7 | 334 | 48.0 | 3.63 | X1934 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.UP2 | 75.7 | 334 | 46.9 | 3.55 | X3511 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| a_51528_63984 | 92.8 | 400 | 38.1 | 3.54 | X2274 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| XMUX.VP4 | 76.9 | 335 | 45.7 | 3.52 | X283 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.VP3 | 69.5 | 328 | 50.5 | 3.51 | X3662 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.VP7 | 69.2 | 327 | 50.5 | 3.49 | X2380 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.VP1 | 77.3 | 335 | 43.7 | 3.38 | X4329 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.UP3 | 67.9 | 326 | 48.8 | 3.31 | X1291 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XMUX.UP5 | 78.7 | 337 | 42.1 | 3.31 | X133 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XSER.XCK.QKN1 | 37.7 | 227 | 87.2 | 3.29 | X3595 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XCTL.DC | 33.5 | 205 | 97.0 | 3.25 | X4797 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XMUX.UP7 | 70.9 | 329 | 44.3 | 3.14 | X4700 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output |
| XSER.XH7_1.CK | 45.6 | 242 | 63.3 | 2.89 | X1898 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XCK.QKN0 | 39.6 | 268 | 68.1 | 2.70 | X2817 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| MAIN_BIAS | 40.7 | 71 | 63.9 | 2.60 | X1468 pfet_03v3 W=8u L=0.28u (562 ohm) | no | static code / bias / test line: DC after settling (low criticality unless switched at speed) |
| XSER.XH6_1.CK | 45.6 | 242 | 54.8 | 2.50 | X1304 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XL7.LD | 38.4 | 696 | 62.9 | 2.41 | X828 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| a_35202_63288 | 57.8 | 130 | 41.7 | 2.41 | X15 nfet_03v3 W=2u L=0.28u (1000 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| XSER.XL6.LD | 38.4 | 696 | 62.7 | 2.41 | X2321 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL3.LD | 38.4 | 696 | 62.6 | 2.40 | X4599 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL2.LD | 38.4 | 696 | 62.4 | 2.40 | X1420 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL5.LD | 38.4 | 696 | 62.4 | 2.39 | X342 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL1.LD | 38.4 | 696 | 62.3 | 2.39 | X4855 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL4.LD | 38.4 | 696 | 62.2 | 2.39 | X2306 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL0.LD | 38.4 | 696 | 62.2 | 2.39 | X2651 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XCK.QDN | 35.7 | 186 | 65.5 | 2.34 | X2566 nfet_03v3 W=4u L=0.28u (500 ohm) | no | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XL7.LDB | 38.6 | 607 | 59.1 | 2.28 | X4174 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL6.LDB | 38.6 | 607 | 59.1 | 2.28 | X1679 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL5.LDB | 38.6 | 607 | 58.9 | 2.27 | X3672 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL3.LDB | 38.6 | 607 | 58.9 | 2.27 | X2808 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL1.LDB | 38.6 | 607 | 58.8 | 2.27 | X3110 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL2.LDB | 38.6 | 607 | 58.8 | 2.27 | X5103 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL4.LDB | 38.6 | 607 | 58.7 | 2.27 | X349 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| XSER.XL0.LDB | 38.6 | 607 | 58.7 | 2.27 | X850 nfet_03v3 W=4u L=0.28u (500 ohm) | no | serializer load/reset control: RC delays the parallel-load window against the phase clocks |
| a_55352_63184 | 75.4 | 339 | 29.8 | 2.25 | X1704 nfet_03v3 W=4u L=0.28u (500 ohm) | no | internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps |
| XSER.XH4_1.CK | 45.6 | 242 | 45.7 | 2.08 | X189 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
| XSER.XH5_1.CK | 45.6 | 242 | 43.9 | 2.00 | X2877 nfet_03v3 W=4u L=0.28u (500 ohm) | yes | register clock / clock-divider net: RC delays & skews the clock edge |
