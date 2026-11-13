# Power delivery: budget, islands, grid, decap, rails, bonds

Owner: power delivery (PD2), 2026-11-13. This file is the requirement the v7 floorplan, the blocks and the board are
checked against. Demands on other owners are rows `PD2-*` in `scratch/reviews/interface-changes.md`.
Numbers written `a / b / c` are optimistic / nominal / pessimistic (the sets of `scratch/reviews/integration-m1.md`
section 4, plus the changes in section 8 here). Model and regression: `scratch/integration/m1-pdn/`.

## 0. Status

| Item | State at the pessimistic bound |
| --- | --- |
| Budget against evidence | Reconciled (section 1). The old ceilings (292 / 240 mA) are exceeded in wired, USB, RF TX, duplex and every autonomous-LO case. Restated to 360 / 260 / 340 mA, which hold only with the digital macro at its PWR-DIG requirement; at the macro's measured 81.8 mA five cases exceed the new ceilings too. |
| Island switches | Closes. Ten islands on the five existing verified switch masters; worst drop 18.4 mV of 20 mV at the design current (worst in-envelope current, with 1.25 x on every contribution that is an estimate or a limit); EM at 85 C <= 55 % of the limit. Costs +0.191 mm2 (section 2). |
| Static IR | Closes as a requirement, not as an extraction: worst tap 106.4 mV of 117 mV (9 % margin) with a 15 % / 15 % Metal5 / Metal4 grid, 97.8 mV at 20 %. This is a DC budget; ripple is on top of it (section 7). |
| Decap | **Does not close on decap alone, and closes without margin with the digital demand.** The plan (5.4 nF, 0.39 mm2 of core) gives 394 mV pk-pk at the macro for 60 mA launched in one packet per cycle (limit 150 mV). If the macro's 78.125 MHz component is cut to 10 % of that case it gives 132 mV at the plan's nominal capacitance, 142 mV at the low capacitance corner and 150 mV with every part at 0.7 x. At the macro's measured 81.8 mA only a balanced launch passes (141 mV). No decap this die can hold closes the single-packet case (section 4). |
| QVCO rail | Open: needs a regulator with 49 dB of rejection at 1 MHz and up to 59 dB at 78.125 MHz (51 dB with a two-phase macro). A `pt_pll_vreg` variant gives 23-27 dB (section 5.1). Demand PD2-11. |
| LNA ground | Open: 44 / 62 / 76 dB needed from die VSS to the LNA input; an own ground on the two freed pad sites is decided, the rejection is the RF RX owner's evidence (section 5.2). |
| Ring PLL | Regulated: passes with a two-phase macro (0.35 / 1.2 / 2.2 ps), fails single-phase at the pessimistic end (9.0 ps against 5). Bypass fails in every case (27-110 ps pessimistic against 20): not an operating mode (section 5.3). |
| ADC | Open at 40 MS/s (30-45 dB of unproven supply rejection needed). 39.0625 MS/s removes every 78.125 MHz multiple; recommended as the RF default (section 5.4). |
| D2H rail | Decided: no split on die 1 (section 5.5). |
| Bonds | EM passes at 85 C: worst supply bond 87.5 mA against 125 mA per cell (60 um of Metal2 per cell, DRM 14.2 limit 2.09 mA/um). Fails at the 125 C column (40 mA), which is not the sign-off temperature. One south supply bond is recommended; which signal gives way is a user decision (section 6). |
| PSRR evidence | Demand rows PD2-14..19 with the spectrum at each tap (section 7). |

## 1. Budget reconciled against current block evidence

Source of every number: `spec/budgets/power_budget.py` (`MEASURED`, `pd2_reconcile`; `--reconcile` prints these
tables, `power-budget.json:pd2_reconciliation` holds them). "Budget" is `analog-architecture.json`
`current_budget_ma` of the blocks the row replaces, in the case shown. "Worst" is the worst value inside the envelope
(tt/ss/ff, 22-32 C, 3.15-3.35 V). Views: ext = extracted, sch = schematic, est = no bench exists, lim = owner's limit.
Cases: W wired 2.5 Gb/s with the on-chip PLL (ring 625 MHz), U USB HS, T TMDS (TX only), RX / TX / DX = RF receive /
transmit / duplex, suffix e = external LO, a = autonomous LO.

| Block | Island | Case | Budget (mA) | Measured nominal | Worst in-envelope | View | Source |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| lna | rf_rx | RXe | 11.85 | 18.90 | 21.40 | lim | limit 18.9 / 11.7 (RC-16u, characterize.py); withdrawn candidate 19.37 / 11.90 tt, 21.40 / 13.43 ff/22/3.35 (scratch/rf-lna-p/v8/idd.log); the stage to be built is not measured |
| rxmix_i | rf_rx | RXe | 0.58 | 3.01 | 3.09 | ext | analog/rf_rx/generated/rxmix_i-evidence.json extracted_nominal.idd_a (fork V) |
| rxmix_q | rf_rx | RXe | 0.58 | 3.01 | 3.09 | ext | same, rxmix_q |
| bbfilter_i | rf_rx | RXe | 3.77 | 5.22 | 5.32 | ext | analog/rf_rx/generated/bbfilter_i-evidence.json extracted_nominal.idd_a |
| bbfilter_q | rf_rx | RXe | 3.77 | 5.22 | 5.32 | ext | same, bbfilter_q |
| txsum | rf_tx | TXe | 2.02 | 2.01 | 2.03 | ext | rf_tx-sim-ext.json chain_dc supply_mA.txsum (carries both txmix tails) |
| rfdriver | rf_tx | TXe | 61.70 | 58.40 | 61.70 | ext | rf_tx-sim-ext.json chain_zero 58.40, scratch/rf-tx-d3/imax.json 61.694 ff/22/3.35 overdriven; TOTAL incl. the board feed: die rail = 0.393 x total (22.9 / 24.3 mA), board feed through the RF_TX pads = 0.607 x total, returning through die VSS |
| adc_i | conv | RXe | 8.00 | 5.73 | 6.30 | ext | converters/generated/adc_i-evidence.json 5.731 at 40 MS/s; no corner current recorded: worst = 1.1 x (assumed) |
| adc_q | conv | RXe | 8.00 | 5.72 | 6.30 | ext | adc_q-evidence.json 5.721; worst assumed 1.1 x |
| dac_i | conv | TXe | 2.00 | 2.07 | 2.28 | ext | dac_i-evidence.json 2.069; worst assumed 1.1 x |
| dac_q | conv | TXe | 2.00 | 2.07 | 2.28 | ext | dac_q-evidence.json; worst assumed 1.1 x |
| refbuf | conv | RXe | 1.56 | 1.56 | 1.56 | ext | refbuf-evidence.json quiescent 0.553 (0.556 ff) + 1.0 mA delivered-reference allowance |
| qvco | lo | RXa | 12.00 | 23.50 | 25.00 | ext | scratch/lo/r5_pn/ext12.json i_vdd_ma 22.11-25.01 over four tank cases (no tt/27 run of r6b) |
| lo_pfdcp | lo | RXa | none | 1.00 | 1.50 | est | LO-INTEGRATION.md section 3: order 1 mA, not measured |
| lo_vreg | lo | RXa | none | 0.50 | 1.00 | est | VDD_LO regulator quiescent: allowance (PD2-11), no design yet |
| lo_mmd | lod | RXa | none | 26.30 | 34.80 | ext | scratch/lo/r4_loop/f/mmdxA.json, mmdxB.json idd_ma at 3.1 GHz: tt 25.8-26.3, ff/22/3.35 34.76, ss 18.8-19.3 (24.3-25.1 tt at 2.4-2.45 GHz in the logs) |
| qvco_pre | lod | RXa | none | 3.00 | 4.00 | est | LO-INTEGRATION.md section 3: lo_qvco.VDDB PRE buffer, "a few mA" of 2.4 GHz CMOS current, not measured |
| lo_mmd_qdum | lod | RXa | none | 8.00 | 10.00 | est | LO-INTEGRATION.md: ~8 mA by design (two 2.6 mA latches + followers), not measured |
| lo_ext | lod | RXe | 18.83 | 11.30 | 13.74 | ext | scratch/timing/lo_ext/results.json internal 11.05 / 13.65; scratch/lo/r4_lo11/results.json external via the CML driver 11.2-11.3 / 13.74 (published lo_ext-evidence.json 16.02 is stale) |
| pll_cdr | pll | W | 3.97 | 6.94 | 10.20 | ext | timing/generated/pll_ring-evidence.json i_on_ma 6.94 at 625 MHz, host_follow 6.85; no corners on the r9v cell: worst = older supply sweep 10.2 (pll_vreg/evidence/pll_ring-f-vs-supply.json) |
| pll_tx | pll | W | 3.97 | 6.94 | 10.20 | est | pt_pll_ring_core has NO current evidence: taken equal to pll_cdr |
| pll_misc | pll | W | none | 1.00 | 2.00 | est | pt_cdr analog cell + pt_pll_vreg2 quiescent: not in any evidence file |
| clockmux | pll | W | 9.67 | 1.35 | 1.55 | ext | timing/generated/clockmux-evidence.json (9.67 mA budget is not in the current file) |
| wordclk | pll | W | 10.48 | 2.30 | 2.42 | ext | timing/generated/wordclk-evidence.json 1.18-2.30, 2.42 ff/32/3.35 (no clocktree evidence exists) |
| rx_ref_in | raw ring | W | 3.55 | 3.49 | 4.63 | ext | timing/generated/diff_clk_rx-evidence.json 3.49 at 100 MHz, 4.63 ff/32/3.35; on the always-on core rail at the REF pad (LO-INTEGRATION.md), not on the pll island; off in the external-LO cases (REF_IN carries the LO) |
| prescale | pll | RXe | none | 1.99 | 2.40 | ext | timing/generated/prescale-evidence.json 1.99 at 2.5 GHz /16, tt only: worst assumed 1.2 x |
| ctle | wired_rx | W | 5.33 | 4.91 | 5.31 | ext | wired_rx/generated/ctle-evidence.json |
| slicer | wired_rx | W | 16.10 | 7.25 | 9.80 | ext | slicer-evidence.json iavg 7.25 at 625 quarter, 6.33 USB HS; worst = 32.2 mW at 810 quarter; USB worst assumed |
| detect | wired_rx | W | 1.66 | 2.31 | 2.38 | ext | detect-evidence.json |
| termination | wired_rx | W | 1.23 | 1.25 | 1.56 | ext | termination-evidence.json idd_div |
| rxlevel | wired_rx | W | 0.04 | 0.03 | 0.04 | ext | rxlevel-evidence.json |
| rxselect | wired_rx | W | 2.00 | 2.00 | 2.00 | est | no active current in rxselect-evidence.json: the 2 mA allocation is kept |
| vthdac | wired_rx | W | none | 0.53 | 0.70 | ext | vthdac-evidence.json extracted i_uA |
| ctle_follower | wired_rx | W | none | 6.30 | 6.90 | est | MW-13-FIX (interface-changes.md): proposed CTLE r4 source followers, 3 mA/side + 0.3 mA bias; not implemented, awaiting approval; worst assumed 1.1 x |
| ptrim | wired_cap | W | none | 18.00 | 21.00 | est | MW-14-FIX (interface-changes.md): pt_ptrim redesign in progress, 18-21 mA for 8 channels at 625 MHz; published cell not functional; USB scaled by 480/625 |
| wrx_cap | wired_cap | W | none | 44.78 | 46.64 | ext | staged r7 scratch/wired_rx/r7cap/stage/results.json 44.78 at 625 MHz (45.15 ff), 34.87 at 480; worst = published r5h wrx_cap-evidence.json ext_q625 46.64 (corner not recorded; schematic 19.78); USB worst assumed 1.05 x |
| wiredtx | wired_tx | W | 36.00 | 35.30 | 37.46 | ext | scratch/wired_tx/sim-results.json cornerq2.5 33.21 ss - 37.46 ff/22/3.35 (no tt run: nominal = mid), int_tmds_q1g485 29.90 |
| usbhs | wired_tx | U | 24.00 | 18.20 | 20.00 | ext | analog/pads/README.md 16.9-18.2 mA after trim; worst assumed 1.1 x |
| bias | raw ring | W | 1.40 | 0.40 | 0.52 | sch | core_support/README.md 0.30-0.52 over the function window |
| aosc | raw ring | W | 0.22 | 0.38 | 0.48 | ext | timing/generated/aosc-evidence.json i_on_ma (register reset = enabled) |
| usbfs | raw ring | U | 8.00 | 8.00 | 8.00 | est | allocation (provider pad drivers), no bench |

Mode totals (mA). The digital macro is 72.1 mA on the newest routed run (AC1_R4, vectorless) and 81.8 mA on CLOSE_R2;
the requirement PWR-DIG is 60 mA (wired/USB) and 40 mA (RF). Host IO is 95.2 mA typical, 116.8 mA at 8 pF, halved in RF
(PWR-HOST-RF).

| Case | Analog nominal | Analog worst | Total nominal (digital 72.1) | Total worst (digital 81.8) | Total worst, digital at PWR-DIG | of which board feed | Old ceiling | New ceiling | Margin at PWR-DIG | Margin at 81.8 mA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W | 145.5 | 165.8 | 312.8 | 364.4 | 342.6 | 0.0 | 292 | 360 | +17.4 | -4.4 |
| U | 110.1 | 126.7 | 277.4 | 325.4 | 303.6 | 0.0 | 292 | 360 | +56.4 | +34.6 |
| T | 42.8 | 49.6 | 210.2 | 248.2 | 226.4 | 0.0 | 292 | 360 | +133.6 | +111.8 |
| RXe | 71.0 | 82.5 | 190.7 | 222.7 | 180.9 | 0.0 | 240 | 260 | +79.0 | +37.3 |
| RXa | 136.8 | 163.5 | 256.5 | 303.7 | 261.9 | 0.0 | 240 | 340 | +78.1 | +36.3 |
| TXe | 116.9 | 130.2 | 236.6 | 270.4 | 228.6 | 37.5 | 240 | 260 | +31.4 | -10.4 |
| TXa | 182.7 | 211.2 | 302.4 | 351.4 | 309.6 | 37.5 | 240 | 340 | +30.4 | -11.4 |
| DXe | 128.3 | 142.8 | 248.0 | 283.0 | 241.2 | 37.5 | 240 | 260 | +18.8 | -23.0 |
| DXa | 194.1 | 223.8 | 313.8 | 364.0 | 322.2 | 37.5 | 240 | 340 | +17.8 | -24.0 |
| stopped | 0.8 | 1.0 | 3.8 | 4.0 | 4.0 | 0.0 | 292 | 360 | +356.0 | +356.0 |

What the reconciliation changes:

- **Announced by the wired RX owner and booked as estimates (not built yet):** `pt_ptrim` redesign 18-21 mA (MW-14-FIX)
  and the CTLE source followers 6.3 mA (MW-13-FIX). They add 27 mA to the wired case.
- **Not in any budget before:** `pt_wrx_cap` 44.8-46.6 mA, the LO chain (QVCO 23.5-25, `lo_mmd` 26.3-34.8,
  `lo_mmd_qdum` about 8, QVCO buffer about 3, `lo_pfdcp` about 1), `vthdac`, and `lo_ext` in the external-LO case
  (11.3-13.7 mA through the CML driver against a 0.19 mA override that describes the passive bench path).
- **Over-booked:** clockmux 9.67 mA booked against 1.35-1.55 measured, clocktree 10.48-12 against 2.3-2.4, slicer 16.1
  against 7.25-9.8, usbhs 24 against 18.2. About 26 mA in wired mode.
- **rfdriver:** 61.7 mA is the total. 61 % of it is the output-pair tail, which enters through the RF_TX pads from the
  board chokes (35.3 of 58.15 mA in `rf_tx-sim-ext.json:safe_en_lo_stopped`, the only bench that separates the two).
  The die rail carries 22.9 / 24.3 mA. The board share still returns through the die ground bonds.
- **M1 figures corrected:** rf island 99.1 mA becomes 56.5 mA on the die rail; `lo_ext` 16 mA was a stale file (11.3-13.7);
  polyphase 2.8 mA is not part of the LO chain; `lo_mmd` 34 mA is the ff corner (26.3 tt).
- **Old ceilings:** wired 292 mA is exceeded by 51 mA with the digital macro at its requirement (342.6 mA worst) and by
  72 mA at 81.8 mA; USB by 12 mA. Autonomous RF was a known exception; duplex with the external LO is 241 mA against 240.
- **Restated ceilings** (`PD2_CEILING_MA`): wired/USB 360 mA, RF with external LO 260 mA, RF with autonomous LO 340 mA:
  total chip current including the rfdriver board feed (37.5 mA), for worst in-envelope analog currents **with the
  digital macro at PWR-DIG**, 5 to 8 % above the worst case of each group. With the macro at its measured 81.8 mA,
  wired (364 mA), RF TX (270 / 351 mA) and duplex (283 / 364 mA) exceed them: PWR-DIG is a requirement the die depends
  on, not a preference (PD2-6).
- **Thermal:** 3.35 V x 360 mA + 51 mW = 1.26 W (1.27 W at 364 mA). Required theta(junction to plate) 6.4 C/W. The
  board requirement B2a already asks 5.2 C/W, so nothing new is demanded.
- **Blocks whose current looks wasteful (flagged to their owners, PD2-3; no capability reduced):** `pt_wrx_cap` 44.8 mA
  extracted against 19.8 mA schematic, and `pt_ptrim` adding 18-21 mA to drive it; `lo_mmd` 26-35 mA plus a dummy of
  about 8 mA; wiredtx in TMDS 29.9 mA against a 16 mA plan; `clk_obs` 4.96 mA each and `vco_replica` up to 11.8 mA; the
  digital macro at 72-82 mA.
- **Evidence gaps that the budget carries as estimates or limits:** `pll_tx` ring core (no current evidence),
  `lo_mmd_qdum`, QVCO buffer, `lo_pfdcp`, the `pt_cdr` analog cell, `pt_pll_vreg2` quiescent, `rxselect`, `pt_ptrim`, the
  CTLE followers, ADC/DAC corner currents, the USB worst values, and the LNA that will be built (18.9 / 11.7 mA are
  limits; 21.4 / 13.4 mA are the ff corner of the withdrawn candidate).

## 2. Islands and switches

The three overloaded islands are split into eight so that each switch sits next to its loads and its supply pad. No new
switch layout: every island uses one of the five verified masters in `analog/island_support` (DRC / LVS clean, full-RC
drop <= 20 mV at the master's design current at all 13 functional points).

Sizing rule: the design current of an island is the sum of the worst in-envelope currents of its blocks, with 1.25 x
on every contribution that is an estimate or a limit and on the rfdriver die-rail share (one bench). At that current
the full-RC worst-corner drop must be <= 20 mV and the current must not exceed the master's design current.

| Island | Worst current (mA) | Design current, 1.25 x on estimates (mA) | Case | Switch master | Master design (mA) | Drop at worst (mV) | Drop at design (mV) | Area (mm2) |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| pll | 26.4 | 29.4 | W | isw_debug | 40 | 10.2 | 11.4 | 0.0370 |
| wired_rx | 28.7 | 30.9 | W | isw_debug | 40 | 11.1 | 12.0 | 0.0370 |
| wired_cap | 67.6 | 72.9 | W | isw_wired | 80 | 16.8 | 18.1 | 0.0641 |
| wired_tx | 37.5 | 37.5 | W | isw_debug | 40 | 14.5 | 14.5 | 0.0370 |
| rf_rx | 38.2 | 43.6 | RXe | isw_rf | 55 | 11.5 | 13.1 | 0.0500 |
| conv | 18.7 | 18.7 | DXe | isw_conv | 30 | 9.0 | 9.0 | 0.0320 |
| lod | 70.6 | 74.1 | RXa | isw_wired | 80 | 17.5 | 18.4 | 0.0641 |
| lo | 27.5 | 28.1 | DXa | isw_conv | 30 | 13.2 | 13.5 | 0.0320 |
| rf_tx | 26.3 | 32.3 | DXa | isw_debug | 40 | 10.2 | 12.5 | 0.0370 |
| debug | 40.0 | 40.0 | debug rule: at most 40 mA of debug loads enabled at once (all on = 51 / 56 mA) | isw_debug | 40 | 15.5 | 15.5 | 0.0370 |

| Island | Members | Enable | Was |
| --- | --- | --- | --- |
| wired_rx | ctle (and its followers), slicer, detect, termination, rxlevel, rxselect, vthdac, RX pad blocks | `wired` | wired (80 mA switch, 133.8 mA worst) |
| wired_cap | `pt_wrx_cap`, `pt_ptrim` | `wired` | wired |
| wired_tx | `pt_wiredtx`, TX pad, USB HS driver | `wired` | wired |
| rf_rx | lna, rxmix_i/q, bbfilter_i/q | `rf` | rf (55 mA switch, 56.5 mA die rail) |
| rf_tx | rfdriver (die-rail part), txmix_i/q, txsum | `rf` | rf |
| lod (VDD_LOD) | `lo_mmd`, `lo_mmd_qdum`, `lo_ext`, `lo_obs`, QVCO buffer | `rf` | pll (60 mA switch; 113.5 mA with lod and lo in RF modes) |
| lo (input of the VDD_LO regulator) | QVCO regulator, QVCO, `lo_pfdcp` | `rf` (PD2-2 asks for its own bit) | pll |
| pll | `pt_pll_vreg2` (both rings), clockmux, wordclk, prescale, `pt_cdr` analog | `pll` | pll |
| conv | adc_i/q, dac_i/q, refbuf | `conv` | unchanged |
| debug | debug blocks; rule: at most 40 mA enabled at once (all on is 51 / 56 mA) | `debug` | unchanged, rule added |

- Area: 0.427 mm2 against 0.236 mm2 today (+0.191 mm2; 0.077 mm2 over the 0.35 mm2 grant). The installed switch capacity
  goes from 265 mA to 475 mA because the island currents went from 204 mA allocated to 382 mA measured or announced.
- The 20 mV rule is taken at the extracted worst-corner resistance. The IR runs of section 3 add another 25 % on the
  switch resistance at the pessimistic end (wired_cap 21.0 mV, lod 21.9 mV there); the 117 mV total still closes.
- Switches that share an enable start together. PG to the register file is the AND of the group; each switch's ISO
  drives its own island's clamps (PD2-2).
- `rx_ref_in` sits on the always-on rail at the REF pad (LO-INTEGRATION.md), not on the pll island.
- **EM at 85 C** (GF180MCU DRM 14.2, the values `analog/core_support` signs off with: Metal1-4 2.09 mA/um, Metal5
  4.5 mA/um, vias 0.58 mA/cut): `isw_wired` at 74.1 mA (lod design current): Metal5 stripes 0.71 mA/um, Metal3 stripes
  alone 1.14 mA/um (55 %), edge bar 0.77 mA/um with the four required feeds, 21 uA per finger. The other masters are
  lower. Hand calculation from `layout.py` geometry, not an extracted current-density run.
- **Soft start at the new loads:** rerun on the extracted masters at each island's worst load, at 3.3 V, tt / ss / ff,
  with the island capacitance of the model and (tt only) 5 x that: 36 transients,
  `analog/island_support/pd2-softstart.json`. Ring dip below its settled value 0 mV; peak switch current 1.00 x the
  island load (1.007 x on conv with 1.25 nF); rail 10-90 % in 1.1-4.8 us; EN to PG <= 8.4 us. Group cases (schematic
  masters, one enable edge): the four RF-side islands draw 156 mA with no overshoot and step the ring by 19 mV; the
  three wired islands 132 mA and 16 mV. That static step is real and lands on every running block (PDN-08: configure
  islands before payload). Negative control: an abrupt gate gives a 92 mV dip and 126 mA peak, and fails. Loads are
  resistors; 3.15 / 3.35 V and 5 x capacitance at ss / ff were not run.
- Drop needs no rerun: every island design current is at or below its master's design current, where the full-RC drop
  is <= 20 mV at all 13 functional points (`analog/island_support/evidence.json`).
- Required of the floorplan (unchanged, ISL-01): ring and island grid strapped to each edge bar at >= 4 evenly spaced
  points or continuously.

## 3. Supply grid the v7 floorplan must implement

Budget: 117 mV DC from the source (3.267 V) to any block tap, supply drop plus ground rise, at the pessimistic set and
worst in-envelope currents with the digital macro at 81.8 mA.

| ID | Requirement | Value |
| --- | --- | --- |
| G1 | Raw VDD and VSS mesh over the whole analog core, over blocks too | Metal5 vertical and Metal4 horizontal straps, **>= 15 % coverage per net on each layer** (sheet <= 0.47 ohm/sq vertical and <= 0.69 ohm/sq horizontal per net at maximum sheet resistance), 20 % wanted (it restores the margin the wired RX additions took), via4 at every same-net crossing |
| G2 | Strap pattern | VDD and VSS straps adjacent (paired), pair pitch <= 70 um, so the loop inductance stays below the 0.4 nH per 250 um square the model assumes at its pessimistic end |
| G3 | Blocks that use Metal4 or Metal5 inside | A VDD/VSS ring of the same total cross-section around them; no gap in the mesh wider than 250 um |
| G4 | Island switch position | VDD edge bar within 150 um of the core ring and within 600 um (along the ring) of a supply pad: wired_cap and wired_rx at pad 18, wired_tx at pad 26, rf_rx at pad 72, rf_tx at pad 58, lod at pad 74, lo at pad 64, pll at pad 35. A switch further in needs a raw-VDD trunk that drops <= 5 mV at the island's design current |
| G5 | Island rails | Metal5 (or Metal5 + Metal4) from the VISL edge bar; **<= 15 mV from the bar to any block supply pin at that block's worst current**; VSS of island blocks is the G1 mesh |
| G6 | Switch-to-block distance | Follows from G5: Metal5 strap width >= 0.47 um per mA per 100 um of length (0.07 ohm/sq). The table below gives the width at the distance the model assumes (blocks above 20 mA within about 500 um of their switch): 107 um for `pt_wrx_cap` at 490 um, 93 um for `pt_wiredtx` at 530 um, 75 um for `lo_mmd` at 460 um, 72 um for the LNA at 720 um |
| G7 | Digital macro | Its VDD/VSS rings tied to the core ring along the whole north and east sides and to the G1 mesh on the west and south sides at <= 80 um pitch; macro internal grid is the digital owner's (PD2-7) |
| G8 | Core ring | 2 x 25 um may narrow to 2 x 12 um (AP4-10b): the provider rails carry the ring current and are uncut (section 6). Cost 0.5-0.9 mV |

Result with G1-G7 at their limits (`e7_static_v7.py`, `out/e7_static_v7_base.txt`), worst taps:

| Tap | Island | mA worst | Drop opt / nom / pess (mV) | Pessimistic split: to switch / switch / strap / ground rise | Metal5 strap for 15 mV at the modelled distance |
| --- | --- | ---: | --- | --- | ---: |
| wrx_cap | wired_cap | 46.6 | 72.6 / 84.3 / 106.4 | 39.5 / 21.0 / 15.0 / 30.9 | 107 um |
| ptrim | wired_cap | 21.0 | 65.2 / 75.8 / 97.9 | 39.5 / 21.0 / 15.0 / 22.4 | 48 um |
| slicer | wired_rx | 9.8 | 56.5 / 65.4 / 88.0 | 34.2 / 13.9 / 15.0 / 24.9 | 17 um |
| wiredtx | wired_tx | 37.5 | 59.3 / 68.5 / 85.9 | 30.5 / 18.2 / 15.0 / 22.2 | 93 um |
| lo_mmd | lod | 34.8 | 52.1 / 60.1 / 91.5 | 34.7 / 21.9 / 15.0 / 19.9 | 75 um |
| lo_ext | lod | 13.7 | 53.5 / 61.6 / 91.7 | 34.6 / 21.9 / 15.0 / 20.2 | 55 um |
| qvco_pre | lod | 4.0 | 55.0 / 63.9 / 94.4 | 34.7 / 21.9 / 15.0 / 22.8 | 42 um |
| lna | rf_rx | 21.4 | 53.4 / 61.2 / 81.7 | 31.7 / 14.4 / 15.0 / 20.6 | 72 um |
| qvco (regulator input) | lo | 25.0 | 53.1 / 61.1 / 78.3 | 23.9 / 16.5 / 15.0 / 22.8 | 74 um |
| rfdriver | rf_tx | 61.7 | 51.6 / 59.0 / 72.9 | 23.3 / 12.7 / 15.0 / 21.8 | 34 um |
| adc_i | conv | 6.3 | 48.1 / 55.0 / 71.5 | 26.7 / 11.2 / 15.0 / 18.6 | 46 um |
| pll_tx | pll | 10.2 | 37.4 / 42.6 / 63.2 | 23.8 / 12.8 / 15.0 / 11.6 | 19 um |
| digital macro | raw | 81.8 | 25.2 / 31.4 / 44.0 | ground rise 18.5 | |
| core_bias | raw | 0.5 | 27.1 / 31.9 / 46.7 | ground rise 19.9 | |

- Margin at the worst tap: 10.6 mV (9 %) at 15 % coverage, 19.2 mV (16 %) at 20 %. The lowest DC rail is 3.161 V at
  `pt_wrx_cap`.
- Coverage sweep at the pessimistic set (worst tap, `out/e7_coverage_sweep.txt`): 8 % fails (134.8 mV), 10 % fails
  (122.9 mV), **15 % 106.4 mV**, 20 % 97.8 mV, 25 % 92.3 mV. 8 % is the negative control.
- Hand check of the worst tap. From first principles: board 0.020 ohm x 364 mA = 7.3 mV; bond and finger trace
  (0.15 + 0.055 ohm) x 87.5 mA = 17.9 mV; switch 0.2484 ohm x 1.25 x 67.6 mA = 21.0 mV; strap 15.0 mV; ground bond
  0.15 ohm x 71.0 mA = 10.7 mV: 71.9 mV. The rest is the model's ring and mesh: 14.3 mV on the supply side and
  20.2 mV on the ground side. Sum 106.4 mV. The bond currents are model outputs too.
- The "opt" and "nom" columns use nominal currents; "pess" uses worst in-envelope currents (not the 1.25 x design
  currents of section 2, which are a switch rule).

## 4. Decap

### 4.1 What the demand is

The macro's ripple is set by its supply-current spectrum against the impedance it sees. The loop inductance is about
0.5 nH, so 3-9 nF of die capacitance puts the anti-resonance at 70-100 MHz, next to the 78.125 MHz launch rate. With
the stiff v7 grid and the uncut ring the damping is lower than M1 assumed (Q 2.3-3.1 instead of 0.9-2.9). The
consequence, at 60 mA with the pessimistic pulse (1.6 ns base) on the worst of the three networks
(`e8_decap_v7.py`, `out/e8_decap_v7.txt`):

| Decap | Total (nF) | Macro pk-pk (mV): single-phase / residual 0.2 / 0.15 / 0.1 / balanced | core_bias pk-pk: single-phase / 0.15 / balanced | f_ar opt / nom / pess (MHz) | Q (pess) |
| --- | ---: | --- | --- | --- | ---: |
| Intrinsic only (negative control) | 0 | 1549 / 686 / 633 / 579 / 471 | 1409 / 573 / 428 | 162 / 182 / 233 | 4.1 |
| Row fill + bond-site tiles only | 0.9 | 919 / 707 / 694 / 681 / 655 | 766 / 577 / 545 | 137 / 143 / 156 | 3.1 |
| Plan, every part x 0.7 | 3.8 | 365 / 172 / 161 / 150 / 127 | 244 / 124 / 105 | 99 / 95 / 95 | 3.1 |
| Plan with MIM at its 2.0 nF minimum | 4.4 | 373 / 163 / 150 / 137 / 112 | 249 / 111 / 88 | 95 / 92 / 88 | 3.1 |
| Plan with the bank at 0.75 nF | 4.65 | 405 / 174 / 160 / 146 / 117 | 264 / 110 / 85 | 95 / 92 / 88 | 2.8 |
| Plan without the row fill | 4.95 | 407 / 174 / 160 / 145 / 116 | 266 / 105 / 78 | 92 / 88 / 84 | 2.8 |
| Plan without the bond-site tiles | 4.95 | 387 / 161 / 147 / 133 / 105 | 262 / 104 / 77 | 92 / 88 / 84 | 2.8 |
| **Plan** | **5.4** | 394 / 161 / 146 / 132 / 103 | 272 / 100 / 71 | 88 / 84 / 81 | 2.8 |
| Plan, bank 2.0 nF | 5.9 | 361 / 147 / 135 / 122 / 97 | 258 / 92 / 63 | 88 / 81 / 78 | 2.4 |
| Plan, bank 3.0 nF | 6.9 | 282 / 121 / 113 / 104 / 88 | 206 / 75 / 53 | 81 / 78 / 72 | 2.3 |
| Plan, every part x 1.3 | 7.0 | 294 / 124 / 116 / 107 / 90 | 218 / 76 / 52 | 81 / 75 / 72 | 2.4 |
| Plan with MIM 5.0 nF | 7.4 | 286 / 125 / 117 / 109 / 94 | 206 / 72 / 50 | 78 / 75 / 69 | 2.4 |
| 6 nF MOS inside the macro outline (reference, not buildable) | 6 | 156 / 75 / 70 / 66 / 56 | 138 / 65 / 52 | 81 / 78 / 72 | 1.1 |
| 8 nF MOS inside the macro outline (reference, not buildable) | 8 | 113 / 53 / 50 / 48 / 42 | 100 / 48 / 39 | 72 / 66 / 59 | 1.0 |

"Single-phase" is all of the macro's charge in one packet per 12.8 ns cycle. The other columns split the launch
charge over the two half-cycles; the number is what is left of the 78.125 MHz component and its odd harmonics
(0.2 = a 60 / 40 split, 0.15 = 57.5 / 42.5, 0.1 = 55 / 45, 0 = balanced). With the nominal pulse (2.4 ns) the plan
gives 342 / 128 / 115 / 103 / 77 mV. At the low capacitance corner (MIM and tiles x 0.88, row fill 0.30 nF) it gives
395 / 170 / 156 / 142 / 114 mV.

- **Limit used:** 150 mV pk-pk at the macro (+-2.3 %), the figure M1 proposed before any of these runs; the digital
  owner has to confirm it with a matching timing derate (PD2-5).
- **Single-phase 60 mA does not close with any decap this die can hold.** It needs about 8 nF of lossy decap inside
  the macro outline (113 mV). The macro's 0.90 mm2 of free sites hold 0.6 nF as row cells (0.65-0.71 fF/um2) and could
  hold 2.0 nF as 3.3 V tiles (2.33 fF/um2) if consolidated; Metal4/Metal5 inside the macro are used by its routing and
  its grid, so no MIM. More decap outside the macro does not converge on the same result: for a single-phase macro
  3.8, 4.4, 5.4 and 7.0 nF give 365, 373, 394 and 294 mV, because the anti-resonance moves across 78.125 MHz.
- **Single-phase current the plan can carry at 150 mV:** 23-26 mA (pessimistic / nominal pulse).
- **With the 78.125 MHz component at 10 %** (the demand of PD2-6): 132 mV at nominal capacitance (12 % margin), 142 mV
  at the low capacitance corner (5 %), 150 mV with every part at 0.7 x (none). With 15 %: 146 / 156 / 161 mV.
- **At the macro's measured 81.8 mA** the plan gives 180 mV at 10 % and 141 mV balanced (194 / 156 mV at the low
  capacitance corner). The average-current requirement PWR-DIG is therefore part of the closure, not a separate topic.
- So the decap closes only as the pair (plan, PD2-6), and its margin is thin. The alternatives are in section 10.

### 4.2 The plan

| Part | Capacitance | Where | Structure | Density (measured) | Area |
| --- | ---: | --- | --- | --- | --- |
| Row fill | 0.45 nF (0.3-0.6) | Free sites of the digital macro | `pt_decap50_*` in place of library `fillcap` (5 V devices; thin oxide in the rows fails DV.9 / DV.3-8) | 0.65-0.71 fF/um2 against 0.54 for `fillcap` | none (inside the macro) |
| Bond-site tiles | 0.45 nF | Under the provider rail cell of the 24 custom bond sites, between the DVDD / DVSS rails | `pt_decap_tile` (COMP/Poly/Metal1 only) | 2.33 fF/um2 of tile; 0.193 mm2 is free of Metal2 as well (0.495 mm2 if the pad escapes are moved) | none (ring band) |
| Grid MIM | 3.0 nF target, **2.0 nF minimum** | Over the block outlines and channels whose Metal4 / Metal5 are free (2.86 mm2 of outlines per AP4): the G1 straps widened into plates, a Metal5 plate of one net over a Metal4 plate of the other, polarity alternating from band to band so both nets keep both layers | `cap_mim_2f0_m4m5_noshield`, units <= 100 x 100 um, no Via3 under a plate | 1.9 fF/um2 of plate (1.8 / 2.0 / 2.2) | no core area, but Metal4 and Metal5: 1.05 mm2 of plate for 2.0 nF (37 % of the free outline area on both layers), 1.58 mm2 for 3.0 nF (55 %) |
| Macro-edge bank | 1.5 nF | Against the west, south and east edges of the macro, within 250 um | `pt_decap_tile` with MIM above (0.9 nF MOS + 0.6 nF MIM) | 3.9-4.2 fF/um2 stacked | **0.39 mm2** of core |
| Island-local | 1.16 nF in the model (50-250 pF per island) | On each island rail, at the loads | block-internal / MIM | | inside the blocks |

- **What the grid MIM really costs.** A Metal5-vertical / Metal4-horizontal mesh at the G1 minimum overlaps the
  opposite net only at crossings: 4.5 % of the area, 0.85 nF over the whole analog core. 2-3 nF therefore needs plates:
  over free block outlines Metal4 and Metal5 go to 37-55 % coverage for power (the plates are the grid there). The
  plates are cut at every same-net via4 column, and no Via3 may sit under a plate, so a block under a plate reaches
  Metal4 / Metal5 only in the gaps between units (every <= 100 um). This arrangement is rule arithmetic from the
  `mim_b.rb` deck; no layout or DRC run exists for it (PD2-9).
- Core area the plan costs: 0.39 mm2 (decap) + 0.191 mm2 (switches) = 0.58 mm2. AP4 plan D had removed the 0.693 mm2
  of dedicated decap and counted about 0.7 mm2 of slack; this takes 0.58 mm2 of it back (PD2-9).
- Leakage of the whole plan, ff / 85 C / 3.63 V: below 0.4 uA (n-well diode of the pfet tiles, upper bound; MIM 20 pA;
  row cells 40 nA). The PDK MOS models have no gate leakage (`igcmod = 0`); a 1 nA/cm2 defect floor would add 15 pA.
- `pt_decap_tile` real time constant is about 335 ps (152 ps tie device + 175-195 ps of pfet L = 6 um channel that the
  extraction cannot see, because the PDK models have no channel resistance). It still holds its capacitance at 156 MHz
  (wRC = 0.33) and loses most of it above 500 MHz.
- An nfet_03v3 tile with L = 2-5 um would be denser and faster (4.0-4.1 fF/um2 of gate, 5-31 ps, up to 3.0 fF/um2 of
  tile, not laid out). Not needed for the plan; the existing tile's loss is useful damping.

### 4.3 Anti-resonance placement and damping

| Total die decap | Anti-resonance | Verdict |
| --- | --- | --- |
| below 1.5 nF | 140-170 MHz | **Avoid:** on 156.25 MHz (|Z| 1.6-2.5 ohm there) |
| 2-3.5 nF | 100-125 MHz | Between the lines: |Z| 0.6-0.9 ohm at 78.125 MHz and 0.34-0.5 ohm at 156.25 MHz; good for neither |
| **4.4-6 nF (plan: 5.4)** | 78-95 MHz | On 78.125 MHz: |Z| 0.9-1.2 ohm there, 0.23-0.26 ohm at 156.25 MHz. **Right only if the macro's 78.125 MHz component is small (two-phase); wrong for a single-phase macro** |
| 6-9 nF | 60-80 MHz | On 78.125 MHz with lower |Z| (0.8-0.9 ohm) |
| above 12 nF | below 60 MHz | Clear of the clock; not available |

- The plan is built for a macro whose supply current is dominated by 156.25 MHz. If the digital owner cannot deliver
  that (PD2-6), no total between 2 and 7 nF helps: a single-phase 60 mA macro stays at 280-410 mV pk-pk, and the levers
  left are the macro current and the ripple limit (section 10).
- **Damping.** PDN-03 asks for damping when Q exceeds 3. The plan has Q 2.7 / 3.1 / 2.8 with 33 % of its capacitance
  lossy (row cells and tiles); MIM-heavy variants reach 3.1, tile-heavy ones 2.3-2.4. Rule for the floorplan: never
  add MIM without tiles on the same straps, and keep at least one third of the raw-rail capacitance in tiles or row
  cells. The plan's peak is 0.86 / 1.02 / 1.19 ohm: the A2 target of 1 ohm over 20-200 MHz is met at the optimistic
  end only (missed by 0.02 / 0.19 ohm); PKG-06 (2 ohm, 50-400 MHz) is met.
- The 8 COB strip capacitors stay mandatory (BP-4): M1 found every figure 1.2-1.5 x worse without them.

## 5. Rails

### 5.1 QVCO: own regulated rail (VDD_LO)

The QVCO, `lo_pfdcp` and the regulator sit on the `lo` island (30 mA switch master, 13.5 mV at the 28.1 mA design
current), fed from the ring at pad 64. Input of the regulator, pessimistic: 3.19 V DC minimum (78 mV total drop), and
this ripple (`e9_victims_v7.py`, tap `qvco`, mV peak, opt / nom / pess):

| Line | Single-phase digital | Two-phase (residual 0.15) | Allowed at the QVCO for -80 dBc (K = -59.7 MHz/V) | Rejection needed (dB), single / two-phase |
| --- | --- | --- | --- | --- |
| PA envelope 1 MHz (RF TX, assumed 5 / 15 / 30 % of 61.7 mA) | 0.10 / 0.37 / 0.90 | same | 3.35 uV | 29 / 41 / 49 |
| PA envelope 5 / 10 / 20 MHz | 0.10-0.16 / 0.37-0.60 / 0.90-1.46 | same | 16.7 / 33.5 / 67 uV | 35 / 30 / 27 at pess |
| 78.125 MHz, digital macro | 26 / 60 / 160 | 3.9 / 9.1 / 24 | 262 uV | 40 / 47 / 56, two-phase 24 / 31 / 39 |
| 78.125 MHz, D2H at div2 (RF modes) | 5.3 / 24 / 67 | same | 262 uV | 26 / 39 / 48 |
| 80 MHz, ADC conversion current | 13 / 19 / 24 | same | 268 uV | 34 / 37 / 39 |
| 156.25 MHz, digital and D2H | 8.0 / 15 / 37 and 3.3 / 12 / 26 | same | 523 uV | 24 / 29 / 37 and 16 / 27 / 34 |
| 234-312 MHz | 3.4 / 7.2 / 20 | 0.9 / 4.4 / 13 | 0.79-1.05 mV | 13 / 19 / 28 |

Regulator requirement (PD2-11, for the LO owner to design or to refute with a different spur limit):

| Quantity | Requirement |
| --- | --- |
| Rejection, input rail to QVCO supply | >= 50 dB from 100 kHz to 2 MHz; >= 40 dB at 5 MHz falling to 30 dB at 20 MHz; **>= 59 dB at 78.125 MHz** (digital and D2H lines add at the same frequency in RF modes: 227 mV; 51 dB with a two-phase macro; 41 dB with a two-phase macro and D2H at slow slew); >= 40 dB at 80 and 156.25 MHz; >= 30 dB at 234-312 MHz |
| Load | 30 mA (QVCO 25.0 worst + `lo_pfdcp` 1.5 + margin) |
| Input | 3.15 V DC minimum (die floor); 3.19 V at the pessimistic static drop |
| Dropout | Whatever keeps the QVCO inside its tuning range: the LO owner states the minimum VDD_LO; 0.35 V gives 2.80 V |
| Output noise | <= 7 nV/rtHz from 100 kHz to 1 MHz (LO-11, LO-INTEGRATION.md) |
| Line step | PA turn-on moves the input by 4.9 / 7.2 / 11.6 mV (M1), and an island group turning on by 16-19 mV: <= 0.1 mV at the output |
| Ground | QVCO and charge-pump returns star-connected at the regulator's output capacitor (Kelvin), one tie to the VSS mesh |

- **Can a `pt_pll_vreg` variant serve? Not alone.** It is a native follower with 23-27 dB from 10 to 200 MHz at 6 mA
  and 0.31-0.50 V dropout; scaled to 30 mA it keeps that rejection. The need is 49-59 dB (41-51 dB with the digital
  demands met). Two such stages in series reach about 50 dB but cost 0.6-1.0 V. It can be the high-frequency stage
  behind a loop-regulated stage or a cascode.
- A dedicated bond alone (M1: 5-13 dB) is not enough, but pad 64 (PWR_AUX_1) is where the `lo` switch sits, so the
  option of cutting that pad from the ring stays open at no floorplan cost.
- LO20 item 5 states "30 uV at 1 MHz = -80 dBc". With -59.7 MHz/V, 30 uV at 1 MHz is -61 dBc. If -61 dBc is the real
  limit, every figure in the table drops by 19 dB and a single `pt_pll_vreg`-class stage plus two-phase digital is
  enough. The LO owner has to say which one holds.

### 5.2 LNA ground

- Die VSS at the LNA against board ground at 2421.875 MHz (31st harmonic of the D2H div2 comb and the macro) is
  0.34 / 3.0 / 14.6 mV rms. Against -100 dBm (2.24 uV rms) the LNA needs 44 / 62 / 76 dB of rejection from die VSS to
  its input. In duplex the PA puts 2.1 / 7.5 / 21 mV rms at 2.4 GHz on VSS (SUB-07).
- **Decision:** the two in-ring sites freed by RC-16t become AGND_RX down-bonds. The LNA core, its degeneration
  spirals and its input ESD return use AGND_RX only; AGND_RX meets die VSS at one point through the pad-ring ESD
  structure (PD2-12). No tie to the VSS mesh inside the RF RX front end.
- The rejection itself is not in evidence (PD2-15). Until it is, the working set is: D2H slow slew in RF modes (the
  optimistic source set, 44 dB needed), D2H div4 where the payload allows, and 2421.875 MHz out of the channel plan.

### 5.3 Ring PLLs

Ring deterministic jitter, peak, from the ripple at the `pt_pll_vreg2` input (extracted sensitivity 0.045 ps/mV at
78 MHz regulated, 0.55 ps/mV in bypass):

| Case | Regulated (limit 5 ps) | Bypass (limit 20 ps) |
| --- | --- | --- |
| Wired, single-phase digital | 1.5 / 5.0 / 9.0 | 18 / 62 / 110 |
| Wired, two-phase (residual 0.15) | 0.35 / 1.2 / 2.2 | 4.3 / 14 / 27 |
| RF (host_follow ring), single-phase | 2.6 / 5.7 / 13.4 | 32 / 70 / 164 |
| RF, two-phase | 1.4 / 3.1 / 6.6 | 18 / 38 / 81 |

- **Bypass (BYP = 1) is not an operating mode on this rail.** It fails at the pessimistic end even with a two-phase
  macro. It stays as the reset state and as a bench fallback only; firmware clears it before any payload (PD2-13).
- ss / 810 MHz needs bypass (>= 3.02 V at the ring). WT21 already caps production modes at 625 MHz, so 810 MHz is a
  characterization point, not a claim.
- Regulated mode depends on the same digital demand as the decap plan (PD2-6). In RF modes the remaining 6.6 ps comes
  from D2H at 78.125 MHz: D2H slow slew or div4 removes it.
- `pt_pll_vreg2` has no evidence above 200 MHz, where its input carries 2.7 / 11 / 26 mV at 312.5 MHz and up to 14 mV
  at 625 MHz (PD2-17).

### 5.4 ADC clock

- At 40 MS/s the 78.125 MHz multiples alias in band (1.875 MHz, 3.75 MHz, ...). On the conv island the worst aliasing
  line is 25 / 59 / 156 mV (digital, single-phase) or 6.4 / 29 / 78 mV (D2H at div2, which remains with a two-phase
  macro). For a -60 dBFS spur (full scale +-0.87 V) the reference buffer and comparator need 29 / 37 / 45 dB of supply
  rejection, or 17 / 30 / 39 dB with a two-phase macro. None is in evidence (PD2-16).
- At 39.0625 MS/s (78.125 MHz / 2, available today through `conv_sample` = host_follow) every multiple of 78.125 MHz
  lands on DC. What remains is the non-periodic part of the D2H data and the ADC's own conversion current, which is
  synchronous with the sample clock at either rate.
- **Recommendation:** 39.0625 MS/s as the RF default, 40 MS/s kept selectable. Cost: the sample rate is 2.34 % lower,
  so 20 / 40 MHz-channel waveforms need a 128/125 resampler in the FPGA or in the interpolator. That is a spec and
  digital decision (PD2-18); nothing changes in the converters.

### 5.5 D2H rail

Wired mode, 116.8 mA at 8 pF, with the decap plan (`e10_host_bonds_v7.py`), mV pk-pk, opt / nom / pess:

| Option | Host rail | Host-row ground bounce | D2H at the macro | D2H at core_bias |
| --- | --- | --- | --- | --- |
| Common ring (today) | 15 / 72 / 226 | 19 / 147 / 655 | 8 / 34 / 93 | 14 / 64 / 203 |
| + supply pad 13 (bond option A) | 15 / 69 / 218 | 18 / 140 / 617 | 7 / 32 / 89 | 13 / 62 / 200 |
| + supply pad 13 and ground pad 4 (B) | 15 / 72 / 226 | 17 / 127 / 559 | 8 / 34 / 94 | 14 / 65 / 210 |
| + supply 5, 13 and ground 4, 12 | 15 / 73 / 229 | 16 / 119 / 530 | 8 / 34 / 95 | 14 / 65 / 208 |
| Split rail on pads 18, 74 with grounds 9, 19, 73, no own decap | 283 / 2429 / 12658 | 74 / 609 / 2820 | 0 / 1 / 4 | 0 / 2 / 8 |

- **Decision: no D2H rail split on die 1.** A split takes D2H off the core rail (93 to 4 mV at the macro, 203 to 8 mV
  at core_bias, RX spur 16-18 dB better in M1), but (a) it needs at least 1 nF of its own decap at the south pad row
  (0.26 mm2 that does not exist there), without which the split rail is unusable; (b) it takes the two corner supply
  bonds away from the ring, or two more signal pads; (c) it quadruples the host ground bounce unless ground pads are
  added too; (d) it means cutting the provider rails, which are the ESD path and are verified continuous today; (e) the
  RX spur still misses -100 dBm by 21-37 dB at nominal and pessimistic, so the LNA ground of 5.2 is needed anyway.
- What is asked instead (PD2-8): D2H defaults at slow slew and the lowest drive that meets timing, a two-group launch
  stagger, and div4 in RF modes when the payload allows. The optimistic column is that configuration.
- The pessimistic D2H figure at core_bias (203 mV) is as large as the macro's contribution. It is all eleven pins
  toggling together at 156.25 MHz with 0.76 ns edges into 8 pF.

## 6. Bonds

- **Ring continuity, measured** on `scratch/chip-assembly-v5/run2/pt_chip_top.gds`: all four provider rails (DVDD 124.0 um,
  DVSS 101.4 um, VDD 14 um, VSS 14 um, each on Metal3, Metal4 and Metal5) run at full width through all 24 custom bond
  sites, all 74 sites and the four corners; the provider cells are unmodified (XOR empty). The model parameter
  `ring_custom` is 1.0. v6 and later have no GDS, so this has to be rechecked on the v7 assembly.
- DVDD and VDD are one net, tied inside each of the 8 `dvdd` cells; DVSS and VSS likewise in the 10 `dvss` cells.
- **Per-cell rating, measured geometry:** all pad current leaves the bond stack on six Metal2 strips, 60 um in total,
  in both `dvdd` and `dvss`. At the DRM 14.2 limit for 85 C (2.09 mA/um, the column `analog/core_support` signs off
  with) that is **125 mA per cell**; the via stacks are far below their limit. The 60 mA in `power_budget.py` was a
  planning number with no source. At the 125 C column (0.67 mA/um, the value the PDK tech LEF encodes) the cell holds
  40 mA and every bond map below fails; EM sign-off is at 85 C (MANDATE), so this is recorded, not gated. The pads
  owner confirms the Metal2 path and the limit (PD2-10).
- Bond currents with the reconciled loads and the v7 grid (`e7_static_v7.py`, `out/e7_bond_options.txt`), worst case
  wired mode:

| Bond map | Worst supply bond (mA) | Worst ground bond (mA) | Ring drop (mV) | Worst tap (mV) |
| --- | --- | --- | --- | --- |
| Today (8 supply, 10 ground) | 75.6 / 75.9 / 87.5 (pad 18) | 62.7 / 62.2 / 71.0 (pad 19) | 28.2 / 33.3 / 44.6 | 106.4 |
| A: + supply at pad 13 | 55.1 / 55.3 / 63.5 | 62.7 / 62.2 / 71.0 | 23.4 / 27.6 / 36.6 | 100.8 |
| B: + supply 13, ground 4 | 55.1 / 55.3 / 63.5 | 60.6 / 60.1 / 68.3 | 23.0 / 27.0 / 35.9 | 100.1 |
| C: + supply 5 and 13 | 51.9 / 52.1 / 59.6 | 62.7 / 62.2 / 71.0 | 22.7 / 26.7 / 35.5 | 99.8 |
| D: + supply 40, ground 38 (north) | 74.2 / 74.7 / 86.2 | 62.3 / 61.9 / 70.6 | 28.0 / 33.1 / 44.3 | 106.0 |
| E: A + D | 54.2 / 54.5 / 62.6 | 62.3 / 61.9 / 70.6 | 23.3 / 27.4 / 36.4 | 100.4 |

- Today's map passes at 85 C: 87.5 mA is 70 % of the cell rating (ground 71.0 mA, 57 %). M1 found one open supply bond
  adds 5-14 mA to a neighbour, which still passes.
- A south supply bond is the only addition that does something: it removes 24 mA from the worst bond, 8 mV from the
  ring drop and 6 mV from the worst tap, and gives the D2H row (117 mA) its own feed. Dynamically it changes little
  (host rail 226 to 218 mV, ground bounce 655 to 617 mV at the pessimistic end). A north pair does almost nothing,
  because pads 34-37 already sit at the macro.
- Which signal gives way is a user decision (section 10). The board has decoupling footprints only on the 8 existing
  supply nets, so a converted pad has no strip capacitor and is fed from the carrier.
- Ground-bond lengths are still not in `package-channel.json`; the model uses the supply-bond range.

## 7. Supply ripple each block must tolerate (PSRR demands)

The 117 mV of section 3 is a DC budget and the 3.15 V die floor is a DC floor. The ripple below sits on top of it:
at the wired RX taps the DC rail is 3.161-3.18 V at the pessimistic bound and carries 60 mV rms (two-phase macro) to
125 mV rms (single-phase), so the instantaneous rail goes below 3.15 V. Blocks are verified at 3.15 V DC; what they
do with this ripple is exactly the missing evidence the demand rows ask for.

With the decap plan, the v7 grid and the reconciled currents (`e9_victims_v7.py`). Differential rail at the tap, mV
peak of the worst line in each band, opt / nom / pess. "1-ph" is a single-phase macro, "2-ph" is residual 0.15.

| Tap (demand) | Mode | 30-100 MHz, 1-ph | 30-100 MHz, 2-ph | 100-200 MHz | 200-500 MHz | 0.5-1 GHz | 1-6 GHz | rms, 1-ph / 2-ph (pess) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| core_bias: bandgap, biasgen (PD2-14) | wired | 24 / 82 / 145 | 3.5 / 12 / 22 | 8.1 / 23 / 39 | 3.6 / 20 / 61 | 0.27 / 4.0 / 22 | 0.06 / 0.61 / 2.9 | 122 / 64 |
| core_bias | RF | 24 / 55 / 145 | 14 / 27 / 72 | 8.1 / 16 / 39 | 3.5 / 9.8 / 30 | 0.08 / 2.0 / 11 | 0.20 / 1.8 / 18 | 130 / 78 |
| refbuf (PD2-16) | RF RX | 26 / 59 / 156 | 26 / 37 / 78 | 15 / 20 / 38 | 5.8 / 14 / 25 | 0.40 / 4.8 / 15 | 0.04 / 0.32 / 1.5 | 147 / 97 |
| ADC comparator, adc_i tap (PD2-16) | RF RX | 53 / 65 / 156 | 53 / 65 / 77 | 37 / 46 / 52 | 18 / 38 / 50 | 2.3 / 17 / 42 | 0.04 / 0.32 / 1.5 | 203 / 171 |
| lna rail (PD2-15) | RF RX | 24 / 55 / 147 | 14 / 26 / 71 | 8.0 / 15 / 38 | 3.4 / 7.9 / 25 | 0.06 / 1.7 / 10 | 0.05 / 0.23 / 1.6 | 127 / 73 |
| slicer, wired RX (PD2-19) | wired | 25 / 87 / 154 | 3.8 / 13 / 23 | 8.2 / 23 / 38 | 3.5 / 16 / 49 | 1.1 / 8.6 / 24 | 0.26 / 1.9 / 5.8 | 125 / 60 |
| pt_pll_vreg2 input (PD2-17) | wired | 29 / 99 / 174 | 4.4 / 15 / 26 | 8.4 / 24 / 38 | 4.4 / 15 / 27 | 0.19 / 2.6 / 14 | 0.12 / 0.39 / 1.1 | 134 / 50 |
| lo_mmd, VDD_LOD (PD2-11) | RF | 23 / 54 / 144 | 14 / 26 / 71 | 8.0 / 16 / 39 | 3.5 / 9.5 / 30 | 0.07 / 1.9 / 11 | 2.2 / 11 / 49 | 133 / 85 |
| qvco regulator input (PD2-11) | RF TX | 26 / 60 / 160 | 5.3 / 24 / 67 | 8.0 / 15 / 37 | 3.4 / 7.2 / 20 | 0.09 / 1.0 / 5.6 | 0.17 / 0.39 / 1.6 | 129 / 62 |
| wiredtx | wired | 27 / 92 / 162 | 4.0 / 14 / 24 | 8.1 / 23 / 36 | 3.5 / 11 / 27 | 4.6 / 14 / 38 | 6.6 / 20 / 54 | 136 / 74 |
| rfdriver | RF TX | 28 / 64 / 168 | 5.3 / 24 / 66 | 8.2 / 15 / 36 | 3.9 / 8.3 / 22 | 0.17 / 1.5 / 12 | 12 / 29 / 58 | 144 / 80 |
| POR | wired | 25 / 87 / 154 | 3.8 / 13 / 23 | 8.0 / 23 / 37 | 3.4 / 11 / 30 | 0.14 / 2.1 / 13 | 0.05 / 0.32 / 1.7 | 118 / 47 |

- The lines are 78.125 MHz and its multiples (macro; D2H at 156.25 MHz in wired modes and 78.125 MHz in RF modes),
  40 MHz multiples from the ADCs, 625 MHz multiples from `pt_wrx_cap` and `pt_wiredtx`, and 1-20 MHz PA envelope
  (0.1-0.2 / 0.4-0.6 / 0.9-1.5 mV on the lo rail, 2 / 7 / 16 mV on the rf_tx rail).
- The ripple is higher than M1 reported at the analog taps (M1: 49 / 137 / 183 mV pk-pk at core_bias with 3 nF at
  the macro): a stiff grid shares the macro's ripple with everything, and the plan's anti-resonance is near 78 MHz.
  That is the reason the two-phase demand matters to every victim and not only to the macro.
- POR: no false trip (needs >= 1 ms below 1.0-1.5 V; the worst instantaneous rail is above 2.7 V).

## 8. Evidence and regression

- `spec/budgets/power_budget.py --reconcile`: tables of sections 1 and 2; exits non-zero if an island exceeds 20 mV or
  its master's design current, or a case exceeds its ceiling with the macro at PWR-DIG; it also lists the cases over
  the ceiling at the macro's measured current. `--check` (the previous allocation check) still passes and is unchanged.
- `scratch/integration/m1-pdn/`: the M1 scripts `sanity.py`, `e0`-`e6` are the regression. After the PD2 changes
  (`model.py`: optional anisotropic grid and strap override; `core.py`: tap list as a variable; `loads.py`: `pd2*` load
  levels) `sanity.py`, `e0` and `e4_decap_req.py` reproduce their committed outputs exactly, and `e1` / `e6` did so
  until the RF RX owner's budget edit of 22:07 (RC-16u: lna 19.4 -> 18.9 / 11.7 mA, rxmix 6.11 -> 3.01 mA), which
  those scripts read; they now differ from the committed text in the RF cases only (at most 2.3 mV at a tap, 6.7 mA
  of mode current). The committed M1 outputs are left as they were. New: `pd2cfg.py` (islands, positions, grid
  requirement, decap plan), `e7_static_v7.py`, `e8_decap_v7.py`, `e9_victims_v7.py`, `e10_host_bonds_v7.py`,
  `pd2_lines.py`, `e2_peaks.py`.
- Bench proof: `sanity.py` (divider, RLC against closed form and ngspice, coupled bonds) and `e0_sanity_model.py` pass.
  Negative controls that fail as they must: grid at 8 % (134.8 mV) and 10 % (122.9 mV), intrinsic decap only (1549 mV),
  row fill + bond sites only (919 mV), an abrupt switch gate (92 mV ring dip), M1's one-bond case.
- Differences from the M1 model: `ring_custom` 1.0 (measured), reconciled loads, re-partitioned islands with switches
  at the ring, rfdriver board feed 60.7 %, `pt_decap_tile` time constant 335 ps instead of 152 ps. The interior grid
  inductance (0.1 / 0.2 / 0.4 nH per square) and every aggressor spectrum are M1's.
- Decap densities and leakage: ngspice with the PDK models, bench proven on an ideal 1 pF and 1 pF + 50 ohm
  (reads 1.0000 pF, 50.0 ohm; open and 500 ohm cases read differently). Row-cell figure 0.541 fF/um2 reproduced (0.542).
- Soft start: `analog/island_support/pd2_softstart.py`, `pd2-softstart.json`.
- Independent review (a separate agent, given the files and not the conclusions): two blockers and thirteen
  should-fix items, all taken. The blockers were the grid MIM described as strap crossings (which give 0.85 nF, not
  3 nF: now plates over free outlines, with their Metal4 / Metal5 cost stated) and "decap closes at 146 mV" stated
  without its tolerance (now: closes only with the digital demand, without margin at the low capacitance bound).
  Also taken: the 1.25 x margin restored on estimated currents (rf_rx moved to the 55 mA master), ceilings shown
  against the macro's measured current, the placement model made consistent with G6, `lo_obs` and the QVCO buffer added
  to lod, `lo_mmd` nominal corrected to the cited file, the bond rating tied to its DRM source, the DC-versus-ripple
  statement of section 7, and every table regenerated from the output files.

## 9. Not verified

- v7 has no layout. Sections 3 and 4 are requirements checked at their limits on a 13 x 18 mesh, not extractions. The
  grid, the MIM plates and the tile banks have no layout and no DRC run. The model spreads the grid MIM uniformly over
  the analog core; over block outlines only, its distance to the macro will differ.
- The digital macro's real supply current (average per mode, pulse shape, split between clock domains). Everything in
  section 4 is conditional on PD2-6. A lumped hand model of the single-phase case is very sensitive to the loop
  inductance (about 200 mV at 0.5 nH, 300-440 mV at 0.65 nH, 360-600 mV at 0.8 nH): the 342-394 mV of the mesh model
  is plausible, not precise.
- The rfdriver die-rail share (39.3 %) comes from one bench with the LO stopped; the envelope current of the PA is M1's
  assumption (5 / 15 / 30 %).
- Currents carried as estimates or limits (section 1, last bullet). Six of the ten islands depend on at least one.
- EM is a hand calculation at 85 C; the Metal2 path in the supply cells was measured by one agent on the v5 GDS and
  not re-checked by the reviewer.
- Soft start: resistor loads, 3.3 V only, 5 x island capacitance at tt only; the group cases use schematic masters.
- Everything above 1 GHz (LNA in-band ground voltage, 2.4 GHz columns) is order-of-magnitude, as in M1.
- Victim sensitivities with no evidence remain open (section 7); for those the ripple is given, not a pass or fail.
- Ground-bond lengths; board ground plane ideal; carrier placement not swept.

## 10. Decisions that need the user

1. **South supply bond.** Options: (A) D2H_D[9] (pad 13) becomes a supply pad: D2H loses one of ten data lanes;
   (B) the same plus D2H_D[2] (pad 4) as ground: two lanes; (C) keep the map: nothing fails EM at 85 C, the cost is
   24 mA more on bond 18 (87.5 mA, 70 % of the rating), 8 mV of ring drop and 6 mV at the worst tap (106 mV of 117).
   Recommendation: A if the host link can spare a lane, otherwise C.
2. **Area.** The plan costs 0.58 mm2 of core (0.39 decap bank, 0.19 switches) on a die that is already over, and
   37-55 % of Metal4 / Metal5 over the free block outlines for the grid MIM.
3. **Macro ripple.** 150 mV pk-pk is a proposal, and the plan meets it only with the macro's 78.125 MHz component at
   10 % of a single-packet launch, with 12 % margin at nominal capacitance and none at the low bound. The choices if
   that is not acceptable or not achievable: a lower digital current (23-26 mA single-phase closes; 60 mA does not);
   a larger allowed ripple with a timing derate (342-394 mV at 60 mA single-phase); or a 3 nF bank (0.77 mm2 instead
   of 0.39) for 104 mV at 10 %.
4. **ADC default rate** 39.0625 MS/s in RF modes (section 5.4): changes the RF sample-rate plan.
5. **Ceilings** 360 / 260 / 340 mA (section 1) replace 292 / 240 mA, and hold only with the digital macro at PWR-DIG.
