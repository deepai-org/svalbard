# Power delivery: budget, islands, grid, decap, rails, bonds

The requirement the floorplan, the blocks and the board are checked against. Demands on other owners are rows
`PD2-*` in `scratch/reviews/interface-changes.md`; risks are in [risk-register.md](risk-register.md).
Numbers written `a / b / c` are optimistic / nominal / pessimistic. Model and regression:
`scratch/integration/m1-pdn/` (section 8). Budget script: `spec/budgets/power_budget.py`.

Supply topology: one external supply. The provider ring joins all eight supply bonds into one net and all ten
ground bonds into another; named supply sites are labels, not isolated feeds. Ten switched islands hang off the
ring; the digital macro, the host pads and the always-on core (POR, bias, oscillator, reference receiver) are on
the raw ring. Operating window 3.15-3.35 V at the die; slow dies may be trimmed up to a 3.50 V setpoint.

## 0. Status

| Item | State at the pessimistic bound |
| --- | --- |
| Budget | Mode ceilings 360 / 260 / 340 mA (wired and USB / RF with external LO / RF with on-chip LO). They hold only with the digital macro at its PWR-DIG requirement; at the macro's last measured 81.8 mA five cases exceed them (section 1). |
| Island switches | Closes. Ten islands on the five verified switch masters; worst drop 18.4 mV of 20 mV at the design current; electromigration at 85 C <= 55 % of the limit (section 2). |
| Static drop | Closes as a requirement, not as an extraction: worst tap 106.4 mV of 117 mV with a 15 % / 15 % Metal5 / Metal4 grid, 97.8 mV at 20 % (section 3). Ripple is on top of it (section 7). |
| Decap | **Does not close on decap alone, and closes without margin with the digital demand.** The plan (5.4 nF) gives 394 mV pk-pk at the macro for 60 mA launched in one packet per cycle (limit 150 mV), and 132 / 142 / 150 mV if the macro's 78.125 MHz component is cut to 10 % of that case. The plan depends on the digital macro's real current shape, which is not known (section 4). After the block repacks the free area over blocks holds only 1.1-1.4 nF of grid MIM against the 2.0 nF minimum. |
| QVCO rail | Open: own regulated rail; the regulator is to be requalified against the -60 dBc per tone spur limit and shrunk (section 5.1, PD2-11). |
| LNA ground | Open: 44 / 62 / 76 dB needed from die VSS to the LNA input. The LNA uses die VSS; no separate ground pad is possible on the fixed bond layout (section 5.2). |
| Ring PLL | Regulated: passes with a two-phase macro (0.35 / 1.2 / 2.2 ps), fails single-phase at the pessimistic end (9.0 ps against 5). Regulator bypass is not an operating mode (section 5.3). |
| ADC | Default sample rate 39.0625 MS/s in RF modes, which puts every 78.125 MHz multiple on DC; 40 MS/s stays selectable and needs 30-45 dB of unproven supply rejection (section 5.4). |
| D2H rail | No split (section 5.5). |
| Bonds | Fixed map, 8 supply and 10 ground bonds. Electromigration passes at 85 C: worst supply bond 87.5 mA against 125 mA per cell (section 6). |
| Supply rejection evidence | Missing for every victim; demand rows PD2-14..19 with the spectrum at each tap (section 7). |
| Supply trim | Regulator stack-up for the 3.50 V setpoint and reliability at 3.5 V are not evaluated. |

## 1. Budget against block evidence

Source of every number: `spec/budgets/power_budget.py` (`--reconcile` prints these tables;
`power-budget.json:pd2_reconciliation` holds them). "Budget" is `analog-architecture.json` `current_budget_ma`.
"Worst" is the worst value inside the window (tt/ss/ff, 22-32 C, 3.15-3.35 V). Views: ext = extracted,
sch = schematic, est = no bench exists, lim = owner's limit. Cases: W wired 2.5 Gb/s with the on-chip PLL (ring
625 MHz), U USB HS, T TMDS (TX only), RX / TX / DX = RF receive / transmit / duplex, suffix e = external LO,
a = on-chip LO.

| Block | Island | Case | Budget (mA) | Measured nominal | Worst in-envelope | View | Source |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| lna | rf_rx | RXe | 11.85 | 18.90 | 21.40 | lim | owner limit 19.0 / 11.8 mA (RX / low-bias); 21.40 / 13.43 at ff/22/3.35 on the last simulated candidate (scratch/rf-lna-p/v8/idd.log); the LNA is not closed |
| rxmix_i | rf_rx | RXe | 0.58 | 3.01 | 3.09 | ext | analog/rf_rx/generated/rxmix_i-evidence.json extracted_nominal.idd_a |
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
| lo_vreg | lo | RXa | none | 0.50 | 1.00 | est | VDD_LO regulator quiescent: allowance (PD2-11) |
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
| ctle_follower | wired_rx | W | none | 6.30 | 6.90 | est | CTLE source followers (approved, MW-13-FIX), 3 mA/side + 0.3 mA bias; not built; worst assumed 1.1 x |
| ptrim | wired_cap | W | none | 18.00 | 21.00 | est | pt_ptrim real-load redesign (MW-14-FIX), 18-21 mA for 8 channels at 625 MHz; not built; USB scaled by 480/625 |
| wrx_cap | wired_cap | W | none | 44.78 | 46.64 | ext | staged r7 scratch/wired_rx/r7cap/stage/results.json 44.78 at 625 MHz (45.15 ff), 34.87 at 480; worst = published r5h wrx_cap-evidence.json ext_q625 46.64 (corner not recorded; schematic 19.78); USB worst assumed 1.05 x |
| wiredtx | wired_tx | W | 36.00 | 35.30 | 37.46 | ext | scratch/wired_tx/sim-results.json cornerq2.5 33.21 ss - 37.46 ff/22/3.35 (no tt run: nominal = mid), int_tmds_q1g485 29.90 |
| usbhs | wired_tx | U | 24.00 | 18.20 | 20.00 | ext | analog/pads/README.md 16.9-18.2 mA after trim; worst assumed 1.1 x |
| bias | raw ring | W | 1.40 | 0.40 | 0.52 | sch | core_support/README.md 0.30-0.52 over the function window |
| aosc | raw ring | W | 0.22 | 0.38 | 0.48 | ext | timing/generated/aosc-evidence.json i_on_ma (register reset = enabled) |
| usbfs | raw ring | U | 8.00 | 8.00 | 8.00 | est | allocation (provider pad drivers), no bench |

Mode totals (mA). The digital macro is 72.1 mA (vectorless, run AC1_R4) to 81.8 mA (run CLOSE_R2); neither is
the current RTL. Host IO is 95.2 mA typical, 116.8 mA at 8 pF, halved in RF modes.

| Case | Analog nominal | Analog worst | Total nominal (digital 72.1) | Total worst (digital 81.8) | Total worst, digital at PWR-DIG | of which board feed | Ceiling | Margin at PWR-DIG | Margin at 81.8 mA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W | 145.5 | 165.8 | 312.8 | 364.4 | 342.6 | 0.0 | 360 | +17.4 | -4.4 |
| U | 110.1 | 126.7 | 277.4 | 325.4 | 303.6 | 0.0 | 360 | +56.4 | +34.6 |
| T | 42.8 | 49.6 | 210.2 | 248.2 | 226.4 | 0.0 | 360 | +133.6 | +111.8 |
| RXe | 71.0 | 82.5 | 190.7 | 222.7 | 180.9 | 0.0 | 260 | +79.0 | +37.3 |
| RXa | 136.8 | 163.5 | 256.5 | 303.7 | 261.9 | 0.0 | 340 | +78.1 | +36.3 |
| TXe | 116.9 | 130.2 | 236.6 | 270.4 | 228.6 | 37.5 | 260 | +31.4 | -10.4 |
| TXa | 182.7 | 211.2 | 302.4 | 351.4 | 309.6 | 37.5 | 340 | +30.4 | -11.4 |
| DXe | 128.3 | 142.8 | 248.0 | 283.0 | 241.2 | 37.5 | 260 | +18.8 | -23.0 |
| DXa | 194.1 | 223.8 | 313.8 | 364.0 | 322.2 | 37.5 | 340 | +17.8 | -24.0 |
| stopped | 0.8 | 1.0 | 3.8 | 4.0 | 4.0 | 0.0 | 360 | +356.0 | +356.0 |

Requirements (traced in `performance-requirements.json`; IDs are defined in [power-partition.md](power-partition.md)):

- **PWR-MODE-CEIL:** total chip current, including the 37.5 mA rfdriver board feed, stays within 360 mA
  (wired, USB), 260 mA (RF, external LO) and 340 mA (RF, on-chip LO) at worst in-window analog currents.
- **PWR-DIG-WIRED / PWR-DIG-RF:** the digital macro draws <= 60 mA in wired and USB modes and <= 40 mA in RF
  modes, unused domains clock-gated, signed off with activity-annotated power. The ceilings depend on it (PD2-6):
  at 81.8 mA wired (364 mA), RF TX (270 / 351 mA) and duplex (283 / 364 mA) exceed them.
- **PWR-HOST-RF:** RF modes run the host link at div2 (`debug.host_link.rate`).
- **PWR-DROP:** <= 117 mV from the source (3.3 V - 1 %) to any block tap, so the die stays >= 3.15 V (section 3).
- **PWR-THERM:** junction 22-32 C across the stopped-to-maximum mode step. 3.35 V x 360 mA + 51 mW = 1.26 W
  needs <= 6.4 C/W from junction to the temperature-controlled surface; board requirement B2a asks 5.2 C/W.
  Stopped power is 15 mW. Not evaluated at the 3.50 V setpoint.

Notes:

- **rfdriver:** 61.7 mA is the total. 61 % of it is the output-pair tail, which enters through the RF_TX pads
  from the board chokes (35.3 of 58.15 mA in `rf_tx-sim-ext.json:safe_en_lo_stopped`, the only bench that
  separates the two). The die rail carries 22.9 / 24.3 mA. The board share returns through the die ground bonds.
- **Estimates and limits the budget carries:** `pll_tx` ring core (no current evidence), `lo_mmd_qdum`, QVCO
  buffer, `lo_pfdcp`, the `pt_cdr` analog cell, `pt_pll_vreg2` quiescent, `rxselect`, `pt_ptrim`, the CTLE
  followers, ADC/DAC corner currents, the USB worst values and the LNA.
- **Currents flagged to their owners as high (PD2-3):** `pt_wrx_cap` 44.8 mA extracted against 19.8 mA
  schematic, and `pt_ptrim` 18-21 mA to drive it; `lo_mmd` 26-35 mA plus a dummy of about 8 mA; wiredtx in TMDS
  29.9 mA; `clk_obs` 4.96 mA each and `vco_replica` up to 11.8 mA; the digital macro.

## 2. Islands and switches

Ten islands, each on one of the five verified switch masters in `analog/island_support` (DRC / LVS clean,
full-RC drop <= 20 mV at the master's design current at all 13 functional points). Instances and enable
groups are in `integration/top/pt_chip.conn`.

Sizing rule: the design current of an island is the sum of the worst in-window currents of its blocks, with
1.25 x on every contribution that is an estimate or a limit and on the rfdriver die-rail share. At that current
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

| Island | Members | Enable |
| --- | --- | --- |
| wired_rx | ctle (and its followers), slicer, detect, termination, rxlevel, rxselect, vthdac, RX pad blocks | `wired` |
| wired_cap | `pt_wrx_cap`, `pt_ptrim` | `wired` |
| wired_tx | `pt_wiredtx`, TX pad, USB HS driver | `wired` |
| rf_rx | lna, rxmix_i/q, bbfilter_i/q | `rf` |
| rf_tx | rfdriver (die-rail part), txmix_i/q, txsum | `rf` |
| lod (VDD_LOD) | `lo_mmd`, `lo_mmd_qdum`, `lo_ext`, `lo_obs`, QVCO buffer | `rf` |
| lo (input of the VDD_LO regulator) | QVCO regulator, QVCO, `lo_pfdcp` | `rf` (PD2-2 asks for its own bit) |
| pll | `pt_pll_vreg2` (both rings), clockmux, wordclk, prescale, `pt_cdr` analog | `pll` |
| conv | adc_i/q, dac_i/q, refbuf | `conv` |
| debug | debug blocks; rule: at most 40 mA enabled at once (all on is 51 / 56 mA) | `debug` |

- Area: 0.427 mm2 of switches; installed capacity 475 mA.
- The section 3 runs add 25 % on the switch resistance at the pessimistic end (wired_cap 21.0 mV, lod 21.9 mV);
  the 117 mV total still closes.
- Switches that share an enable start together. Power-good to the register file is the AND of the group; each
  switch's ISO drives its own island's clamps (PD2-2). The `lo` island needs its own enable bit (PD2-2).
- `rx_ref_in` sits on the always-on rail at the REF pad, not on the pll island.
- **Electromigration at 85 C** (GF180MCU DRM 14.2: Metal1-4 2.09 mA/um, Metal5 4.5 mA/um, vias 0.58 mA/cut):
  `isw_wired` at 74.1 mA: Metal5 stripes 0.71 mA/um, Metal3 stripes alone 1.14 mA/um (55 %), edge bar 0.77 mA/um
  with the four required feeds. Hand calculation from `layout.py` geometry, not an extracted current-density run.
- **Soft start** (`analog/island_support/pd2-softstart.json`, extracted masters, 3.3 V, tt / ss / ff): ring dip
  0 mV; peak switch current 1.00 x the island load; rail 10-90 % in 1.1-4.8 us; EN to PG <= 8.4 us. One enable
  edge on the four RF-side islands draws 156 mA and steps the ring by 19 mV; the three wired islands 132 mA and
  16 mV. That step lands on every running block: configure islands before payload (PDN-08). Loads are
  resistors; 3.15 / 3.35 V were not run.
- Required of the floorplan (ISL-01): ring and island grid strapped to each edge bar at >= 4 evenly spaced points
  or continuously.
- Debug island rule: at most 40 mA of debug loads enabled at once.

## 3. Supply grid the floorplan must implement

Budget: 117 mV DC from the source (3.267 V) to any block tap, supply drop plus ground rise, at the pessimistic
set and worst in-window currents with the digital macro at 81.8 mA.

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

- Margin at the worst tap: 10.6 mV (9 %) at 15 % coverage, 19.2 mV (16 %) at 20 %. The lowest DC rail is
  3.161 V at `pt_wrx_cap`.
- Coverage sweep at the pessimistic set (`out/e7_coverage_sweep.txt`): 8 % fails (134.8 mV), 10 % fails
  (122.9 mV), **15 % 106.4 mV**, 20 % 97.8 mV, 25 % 92.3 mV.
- Hand check of the worst tap: board 0.020 ohm x 364 mA = 7.3 mV; bond and finger trace (0.15 + 0.055 ohm) x
  87.5 mA = 17.9 mV; switch 0.2484 ohm x 1.25 x 67.6 mA = 21.0 mV; strap 15.0 mV; ground bond 0.15 ohm x
  71.0 mA = 10.7 mV: 71.9 mV. The rest is the model's ring and mesh: 14.3 mV on the supply side and 20.2 mV on
  the ground side. Sum 106.4 mV.
- G4 conflicts with signal flow for the lod, pll and wired_tx islands (their loads do not sit at the listed
  supply pads); the strap routing is open.

## 4. Decap

### 4.1 Demand

The macro's ripple is set by its supply-current spectrum against the impedance it sees. The loop inductance
is about 0.5 nH, so 3-9 nF of die capacitance puts the anti-resonance at 70-100 MHz, next to the 78.125 MHz
launch rate (Q 2.3-3.1). At 60 mA with the pessimistic pulse (1.6 ns base) on the worst of the three networks
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
(0.2 = a 60 / 40 split, 0.15 = 57.5 / 42.5, 0.1 = 55 / 45, 0 = balanced). With the nominal pulse (2.4 ns) the
plan gives 342 / 128 / 115 / 103 / 77 mV. At the low capacitance corner (MIM and tiles x 0.88, row fill 0.30 nF)
it gives 395 / 170 / 156 / 142 / 114 mV.

- **Limit used:** 150 mV pk-pk at the macro (+-2.3 %); the digital owner has to confirm it with a matching
  timing derate (PD2-5).
- **Single-phase 60 mA does not close with any decap this die can hold.** It needs about 8 nF of lossy decap
  inside the macro outline (113 mV). More decap outside the macro does not converge: 3.8, 4.4, 5.4 and 7.0 nF
  give 365, 373, 394 and 294 mV, because the anti-resonance moves across 78.125 MHz.
- **Single-phase current the plan can carry at 150 mV:** 23-26 mA.
- **With the 78.125 MHz component at 10 %** (PD2-6): 132 mV at nominal capacitance, 142 mV at the low
  capacitance corner, 150 mV with every part at 0.7 x. With 15 %: 146 / 156 / 161 mV.
- **At 81.8 mA** the plan gives 180 mV at 10 % and 141 mV balanced (194 / 156 mV at the low capacitance corner).
- So the decap closes only as the pair (plan, PD2-6), and its margin is thin. If PD2-6 cannot be met the
  remaining levers are a lower digital current, a larger allowed ripple with a timing derate, or a 3 nF
  macro-edge bank (0.77 mm2 instead of 0.39 mm2, 104 mV at 10 %).

### 4.2 The plan

| Part | Capacitance | Where | Structure | Density (measured) | Area |
| --- | ---: | --- | --- | --- | --- |
| Row fill | 0.45 nF (0.3-0.6) | Free sites of the digital macro | `pt_decap50_*` in place of library `fillcap` (5 V devices; thin oxide in the rows fails DV.9 / DV.3-8) | 0.65-0.71 fF/um2 against 0.54 for `fillcap` | none (inside the macro) |
| Bond-site tiles | 0.45 nF | Under the provider rail cell of the custom bond sites, between the DVDD / DVSS rails (computed for 24 sites; the current pad list has 22) | `pt_decap_tile` (COMP/Poly/Metal1 only) | 2.33 fF/um2 of tile; 0.193 mm2 is free of Metal2 as well (0.495 mm2 if the pad escapes are moved) | none (ring band) |
| Grid MIM | 3.0 nF target, **2.0 nF minimum** | Over the block outlines and channels whose Metal4 / Metal5 are free (2.86 mm2 of outlines per AP4): the G1 straps widened into plates, a Metal5 plate of one net over a Metal4 plate of the other, polarity alternating from band to band so both nets keep both layers | `cap_mim_2f0_m4m5_noshield`, units <= 100 x 100 um, no Via3 under a plate | 1.9 fF/um2 of plate (1.8 / 2.0 / 2.2) | no core area, but Metal4 and Metal5: 1.05 mm2 of plate for 2.0 nF (37 % of the free outline area on both layers), 1.58 mm2 for 3.0 nF (55 %) |
| Macro-edge bank | 1.5 nF | Against the west, south and east edges of the macro, within 250 um | `pt_decap_tile` with MIM above (0.9 nF MOS + 0.6 nF MIM) | 3.9-4.2 fF/um2 stacked | **0.39 mm2** of core |
| Island-local | 1.16 nF in the model (50-250 pF per island) | On each island rail, at the loads | block-internal / MIM | | inside the blocks |

- **Grid MIM.** A Metal5-vertical / Metal4-horizontal mesh at the G1 minimum overlaps the opposite net only at
  crossings: 4.5 % of the area, 0.85 nF over the whole analog core. 2-3 nF therefore needs plates over free
  block outlines, taking Metal4 and Metal5 to 37-55 % coverage there. The plates are cut at every same-net via4
  column, and no Via3 may sit under a plate. This is rule arithmetic from the `mim_b.rb` deck; no layout or DRC
  run exists (PD2-9). With the repacked blocks the free outline area holds 1.1-1.4 nF.
- Core area: 0.39 mm2 (macro-edge bank) + 0.427 mm2 (switches).
- Leakage of the whole plan, ff / 85 C / 3.63 V: below 0.4 uA. The PDK MOS models have no gate leakage.
- `pt_decap_tile` time constant is about 335 ps (152 ps tie device + 175-195 ps of pfet channel that the
  extraction cannot see). It holds its capacitance at 156 MHz and loses most of it above 500 MHz.

### 4.3 Anti-resonance placement and damping

| Total die decap | Anti-resonance | Verdict |
| --- | --- | --- |
| below 1.5 nF | 140-170 MHz | **Avoid:** on 156.25 MHz (|Z| 1.6-2.5 ohm there) |
| 2-3.5 nF | 100-125 MHz | Between the lines: |Z| 0.6-0.9 ohm at 78.125 MHz and 0.34-0.5 ohm at 156.25 MHz; good for neither |
| **4.4-6 nF (plan: 5.4)** | 78-95 MHz | On 78.125 MHz: |Z| 0.9-1.2 ohm there, 0.23-0.26 ohm at 156.25 MHz. **Right only if the macro's 78.125 MHz component is small (two-phase); wrong for a single-phase macro** |
| 6-9 nF | 60-80 MHz | On 78.125 MHz with lower |Z| (0.8-0.9 ohm) |
| above 12 nF | below 60 MHz | Clear of the clock; not available |

- The plan is built for a macro whose supply current is dominated by 156.25 MHz (PD2-6).
- **Damping.** The plan has Q 2.7 / 3.1 / 2.8 with 33 % of its capacitance lossy (row cells and tiles). Rule
  for the floorplan: never add MIM without tiles on the same straps, and keep at least one third of the raw-rail
  capacitance in tiles or row cells. The plan's peak is 0.86 / 1.02 / 1.19 ohm; the package criterion (2 ohm,
  30-400 MHz) is met.
- The eight 1 uF board capacitors are mandatory (BP-4): without them every figure is 1.2-1.5 x worse.

## 5. Rails

### 5.1 QVCO: own regulated rail (VDD_LO)

The QVCO, `lo_pfdcp` and the regulator sit on the `lo` island (30 mA switch master, 13.5 mV at the 28.1 mA
design current), fed from the ring at pad 64. Regulator input, pessimistic: 3.19 V DC minimum (78 mV total
drop). Spur limit at the QVCO: **-60 dBc per tone (0.2 ps)**, K = -59.7 MHz/V. Ripple at the regulator input
(`e9_victims_v7.py`, tap `qvco`, mV peak, opt / nom / pess) and the rejection it implies; the "allowed" and
"rejection" columns are the model's -80 dBc figures shifted by 20 dB:

| Line | Single-phase digital | Two-phase (residual 0.15) | Allowed at the QVCO | Rejection needed (dB), single / two-phase |
| --- | --- | --- | --- | --- |
| PA envelope 1 MHz (RF TX, assumed 5 / 15 / 30 % of 61.7 mA) | 0.10 / 0.37 / 0.90 | same | 33.5 uV | 9 / 21 / 29 |
| PA envelope 5 / 10 / 20 MHz | 0.10-0.16 / 0.37-0.60 / 0.90-1.46 | same | 167 / 335 / 670 uV | 15 / 10 / 7 at pess |
| 78.125 MHz, digital macro | 26 / 60 / 160 | 3.9 / 9.1 / 24 | 2.62 mV | 20 / 27 / 36, two-phase 4 / 11 / 19 |
| 78.125 MHz, D2H at div2 (RF modes) | 5.3 / 24 / 67 | same | 2.62 mV | 6 / 19 / 28 |
| 80 MHz, ADC conversion current | 13 / 19 / 24 | same | 2.68 mV | 14 / 17 / 19 |
| 156.25 MHz, digital and D2H | 8.0 / 15 / 37 and 3.3 / 12 / 26 | same | 5.23 mV | 4 / 9 / 17 and 0 / 7 / 14 |
| 234-312 MHz | 3.4 / 7.2 / 20 | 0.9 / 4.4 / 13 | 7.9-10.5 mV | 0 / 0 / 8 |

Regulator requirement (PD2-11):

| Quantity | Requirement |
| --- | --- |
| Rejection, input rail to QVCO supply | >= 30 dB from 100 kHz to 2 MHz; >= 20 dB at 5 MHz falling to 10 dB at 20 MHz; >= 39 dB at 78.125 MHz (digital and D2H lines add at the same frequency in RF modes: 227 mV; 31 dB with a two-phase macro; 21 dB with a two-phase macro and D2H at slow slew); >= 20 dB at 80 and 156.25 MHz; >= 10 dB at 234-312 MHz |
| Load | 30 mA (QVCO 25.0 worst + `lo_pfdcp` 1.5 + margin) |
| Input | 3.15 V DC minimum (die floor); 3.19 V at the pessimistic static drop |
| Dropout | Whatever keeps the QVCO inside its tuning range: the LO owner states the minimum VDD_LO; 0.35 V gives 2.80 V |
| Output noise | <= 7 nV/rtHz from 100 kHz to 1 MHz (LO-11) |
| Line step | PA turn-on moves the input by 4.9 / 7.2 / 11.6 mV, and an island group turning on by 16-19 mV: <= 0.1 mV at the output |
| Ground | QVCO and charge-pump returns star-connected at the regulator's output capacitor, one tie to the VSS mesh |

- A `pt_pll_vreg`-class native follower gives 23-27 dB from 10 to 200 MHz at 6 mA and 0.31-0.50 V dropout.
  That covers every line above except 78.125 MHz with a single-phase macro; its rejection below 10 MHz is not
  in evidence. The regulator as laid out occupies 0.44 mm2 and is to be requalified and shrunk.
- Pad 64 (PWR_AUX_1) is where the `lo` switch sits.

### 5.2 LNA ground

- Die VSS at the LNA against board ground at 2421.875 MHz (31st harmonic of the D2H div2 comb and the macro) is
  0.34 / 3.0 / 14.6 mV rms. Against -100 dBm (2.24 uV rms) the LNA needs 44 / 62 / 76 dB of rejection from die
  VSS to its input. In duplex the PA puts 2.1 / 7.5 / 21 mV rms at 2.4 GHz on VSS (SUB-07).
- The LNA uses die VSS: the fixed bond layout offers no extra pad, down-bond or double bond, and a ground on a
  standard finger returns through 1.9-7.5 nH (`scratch/reviews/pads-core/wafer-space-consequences.md`). Ground
  site `vss_pads[1]` (bond 71) on its own on-die net is the runner-up, to be used only if the extracted LNA
  shows at least 10 dB net benefit.
- The rejection itself is not in evidence (PD2-15). Until it is, the working set is: D2H slow slew in RF modes
  (the optimistic source set, 44 dB needed), D2H div4 where the payload allows, and 2421.875 MHz out of the
  channel plan.

### 5.3 Ring PLLs

Ring deterministic jitter, peak, from the ripple at the `pt_pll_vreg2` input (extracted sensitivity
0.045 ps/mV at 78 MHz regulated, 0.55 ps/mV in bypass):

| Case | Regulated (limit 5 ps) | Bypass (limit 20 ps) |
| --- | --- | --- |
| Wired, single-phase digital | 1.5 / 5.0 / 9.0 | 18 / 62 / 110 |
| Wired, two-phase (residual 0.15) | 0.35 / 1.2 / 2.2 | 4.3 / 14 / 27 |
| RF (host_follow ring), single-phase | 2.6 / 5.7 / 13.4 | 32 / 70 / 164 |
| RF, two-phase | 1.4 / 3.1 / 6.6 | 18 / 38 / 81 |

- **Bypass (BYP = 1) is not an operating mode.** It fails at the pessimistic end even with a two-phase macro. It
  is the reset state and a bench fallback only; firmware clears it before any payload (PD2-13).
- ss / 810 MHz needs bypass (>= 3.02 V at the ring) at an untrimmed supply.
- Regulated mode depends on the same digital demand as the decap plan (PD2-6). In RF modes the remaining 6.6 ps
  comes from D2H at 78.125 MHz: D2H slow slew or div4 removes it.
- `pt_pll_vreg2` has no evidence above 200 MHz, where its input carries 2.7 / 11 / 26 mV at 312.5 MHz and up to
  14 mV at 625 MHz (PD2-17).

### 5.4 ADC clock

- **Default 39.0625 MS/s in RF modes** (78.125 MHz / 2, `conv_sample` = host_follow): every multiple of
  78.125 MHz lands on DC. What remains is the non-periodic part of the D2H data and the ADC's own conversion
  current. 20 / 40 MHz-channel waveforms need a 128/125 resampler in the host.
- 40 MS/s is selectable. There the 78.125 MHz multiples alias in band (1.875 MHz, 3.75 MHz, ...): the worst line
  on the conv island is 25 / 59 / 156 mV (digital, single-phase) or 6.4 / 29 / 78 mV (D2H at div2). For a
  -60 dBFS spur the reference buffer and comparator need 29 / 37 / 45 dB of supply rejection, or 17 / 30 / 39 dB
  with a two-phase macro. None is in evidence (PD2-16).

### 5.5 D2H rail

Wired mode, 116.8 mA at 8 pF, with the decap plan (`e10_host_bonds_v7.py`), mV pk-pk, opt / nom / pess:

| Option | Host rail | Host-row ground bounce | D2H at the macro | D2H at core_bias |
| --- | --- | --- | --- | --- |
| Common ring | 15 / 72 / 226 | 19 / 147 / 655 | 8 / 34 / 93 | 14 / 64 / 203 |
| Split rail on pads 18, 74 with grounds 9, 19, 73, no own decap | 283 / 2429 / 12658 | 74 / 609 / 2820 | 0 / 1 / 4 | 0 / 2 / 8 |

- **No D2H rail split.** A split takes D2H off the core rail, but it needs at least 1 nF of its own decap at the
  south pad row (0.26 mm2 that does not exist there), takes two corner supply bonds from the ring, quadruples
  the host ground bounce, means cutting the provider rails (the ESD path), and still leaves the RX spur short
  of -100 dBm.
- Instead (PD2-8): D2H defaults at slow slew and the lowest drive that meets timing, a two-group launch stagger
  (`hostio.controls.d2h_stagger`), and div4 in RF modes when the payload allows. The optimistic column is that
  configuration.
- The pessimistic D2H figure at core_bias (203 mV) is all eleven pins toggling together at 156.25 MHz with
  0.76 ns edges into 8 pF.

## 6. Bonds

- The bond map is fixed: 8 supply and 10 ground bonds on the provider sites, 0.8 mil aluminium wire, no added
  or converted supply bonds ([package-channel.md](package-channel.md)).
- **Ring continuity, measured** on `scratch/chip-assembly-v5/run2/pt_chip_top.gds`: all four provider rails
  (DVDD 124.0 um, DVSS 101.4 um, VDD 14 um, VSS 14 um, each on Metal3, Metal4 and Metal5) run at full width
  through all 74 sites and the four corners. To be rechecked on the next assembly.
- DVDD and VDD are one net, tied inside each of the 8 `dvdd` cells; DVSS and VSS likewise in the 10 `dvss` cells.
- **Per-cell rating:** all pad current leaves the bond stack on six Metal2 strips, 60 um in total. At the DRM
  14.2 limit for 85 C (2.09 mA/um) that is **125 mA per cell**. At the 125 C column (0.67 mA/um) the cell holds
  40 mA; sign-off is at 85 C. The pads owner confirms the Metal2 path (PD2-10).
- **Bond currents** (`e7_static_v7.py`, wired mode, opt / nom / pess): worst supply bond 75.6 / 75.9 / 87.5 mA
  (pad 18, 70 % of the cell rating), worst ground bond 62.7 / 62.2 / 71.0 mA (pad 19), ring drop
  28.2 / 33.3 / 44.6 mV. One open supply bond adds 5-14 mA to a neighbour, which still passes. The wire itself
  rises 11.5 K at 87.5 mA.
- The model uses the supply-bond length range for the ground bonds; it has not been rerun with the per-bond
  values now in `package-channel.json`.

## 7. Supply ripple each block must tolerate

The 117 mV of section 3 is a DC budget and the 3.15 V die floor is a DC floor. The ripple below sits on top of
it: at the wired RX taps the DC rail is 3.161-3.18 V at the pessimistic bound and carries 60 mV rms (two-phase
macro) to 125 mV rms (single-phase), so the instantaneous rail goes below 3.15 V. Blocks are verified at 3.15 V
DC; what they do with this ripple is the missing evidence the demand rows ask for.

With the decap plan, the grid of section 3 and the currents of section 1 (`e9_victims_v7.py`). Differential rail
at the tap, mV peak of the worst line in each band, opt / nom / pess. "1-ph" is a single-phase macro, "2-ph" is
residual 0.15.

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

- The lines are 78.125 MHz and its multiples (macro; D2H at 156.25 MHz in wired modes and 78.125 MHz in RF
  modes), 40 MHz multiples from the ADCs at 40 MS/s, 625 MHz multiples from `pt_wrx_cap` and `pt_wiredtx`, and
  1-20 MHz PA envelope (0.1-0.2 / 0.4-0.6 / 0.9-1.5 mV on the lo rail, 2 / 7 / 16 mV on the rf_tx rail).
- A stiff grid shares the macro's ripple with everything, and the plan's anti-resonance is near 78 MHz: the
  two-phase demand matters to every victim, not only to the macro.
- POR: no false trip (needs >= 1 ms below 1.0-1.5 V; the worst instantaneous rail is above 2.7 V).

## 8. Evidence and regression

- `spec/budgets/power_budget.py --reconcile`: tables of sections 1 and 2; exits non-zero if an island exceeds
  20 mV or its master's design current, or a case exceeds its ceiling with the macro at PWR-DIG; it also lists
  the cases over the ceiling at 81.8 mA. `--check` is the allocation check.
- `scratch/integration/m1-pdn/`: `sanity.py` and `e0`-`e6` are the regression; `pd2cfg.py` holds the islands,
  positions, grid requirement and decap plan; `e7_static_v7.py`, `e8_decap_v7.py`, `e9_victims_v7.py`,
  `e10_host_bonds_v7.py` produce sections 3 to 7.
- Bench proof: `sanity.py` (divider, RLC against closed form and ngspice, coupled bonds) and
  `e0_sanity_model.py`. Negative controls that fail as they must: grid at 8 % and 10 %, intrinsic decap only
  (1549 mV), row fill + bond sites only (919 mV), an abrupt switch gate (92 mV ring dip, 126 mA peak).
- Soft start: `analog/island_support/pd2_softstart.py`, `pd2-softstart.json`.

## 9. Not verified

- No layout exists for the grid, the MIM plates or the tile banks, and no DRC run. Sections 3 and 4 are
  requirements checked at their limits on a 13 x 18 mesh, not extractions.
- The digital macro's real supply current (average per mode, pulse shape, split between clock domains).
  Everything in section 4 is conditional on PD2-6. A lumped hand model of the single-phase case is very
  sensitive to the loop inductance (about 200 mV at 0.5 nH, 360-600 mV at 0.8 nH).
- The rfdriver die-rail share (39.3 %) comes from one bench with the LO stopped; the PA envelope current is an
  assumption (5 / 15 / 30 %).
- Currents carried as estimates or limits (section 1). Six of the ten islands depend on at least one.
- Electromigration is a hand calculation at 85 C; the Metal2 path in the supply cells was measured on the v5 GDS.
- Soft start: resistor loads, 3.3 V only; the group cases use schematic masters.
- Everything above 1 GHz (LNA in-band ground voltage, 2.4 GHz columns) is order-of-magnitude.
- Victim supply rejection (section 7): for those the ripple is given, not a pass or fail.
- Supply ramps faster than 10 us fire the provider supply-pad clamps (`scratch/reviews/integration-m6.md`):
  board rule, supply slew <= 0.3 V/us and no hot-plug.
- Everything at the 3.50 V trim setpoint; board ground plane ideal; carrier placement not swept.
