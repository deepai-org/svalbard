# USB 2.0 data path: chip-side integration (pin list and connection intent)

Written 2026-11-13 by the USB sub-owner of wired TX after mode-walk row MW-18 ("USB has no data path in
either direction"). Rows USB-D1.. in `scratch/reviews/interface-changes.md` carry the demands on other
owners; this file is the pin-level statement for chip-top / assembly.

## Parts

| instance | cell | owner | state |
|---|---|---|---|
| `pad_usb` | `pad_wirepad` (top subckt `tx_protected_pad`), `analog/pads/generated/stress-safe-families/wired-receive-usb/` | pads | published (PD47 / PD48c) |
| `usb_txdrv` | `pt_usb_txdrv`, `analog/wired_tx/usbdrv.py`, `generated/usbdrv.*` | wired TX (USB) | **new**, see "State of `pt_usb_txdrv`" below |
| `hsbias` | `pt_wtx_hsbias`, `analog/wired_tx/hsbias.spice` | wired TX | published; `IBIAS` has no source (USB-D7) |
| `wiredtx` | `pt_wiredtx` | wired TX | published; its `CMD_MAIN_P/N` are the HS serial data |
| `rxselect`, `slicer`, `detect`, `termination`, `rxlevel`, `wmon_sel` | wired RX | wired RX | published; consumers missing (USB-D4, USB-D5) |
| USB logic in `pt_digital_macro` | - | digital | **does not exist** (USB-D1, USB-D2) |

Recorded decision used here (`spec/block-diagram.md:33`, `spec/parallel-datapath-candidate.md:23-26`,
`spec/streaming-transport-v2.md:191-206`): the FPGA owns packets (SIE, NRZI, bit stuffing, CRC); the die does the
timed physical actions (serialization, burst capture, turnaround, line drive). So the die needs no SIE, but
it does need the signals below between the digital macro and the analog cells.

## `pt_usb_txdrv` pins

Supply `VDD` = `RAIL_wired` (VDD_WIRED_SW, 3.3 V), `VSS`. Every input is a MOS gate. All outputs are
active high and are low when not enabled.

| pin | dir | connect to | notes |
|---|---|---|---|
| `CMD_P`, `CMD_N` | in | `wiredtx.CMD_MAIN_P`, `wiredtx.CMD_MAIN_N` (nets `TX_MAIN_P/N`) | HS serial data, x4 bit repetition (MODE_F), 2.083 ns bits. `CMD_P` = 1 drives D+ (J). Tap load 10 fF per leg (extracted); the cell must sit within 100 um of the `pt_wiredtx` CMD outputs (the long wires are this cell's outputs, not the CMD nets) |
| `HS_EN` | in | digital, static | `usbdrive.select.branch == hs` AND `usbhs.config.tx_enable` |
| `HS_DRV` | in | digital, timed | 1 while an HS packet is driven; 0 = HS idle (both switches off, line held at 0 V by the terminations). Word-granular is enough (see USB-D1) |
| `FS_EN` | in | digital, static | `usbdrive.select.branch == fsls` AND `usbfs.config.drive_enable` |
| `TX_DP`, `TX_DN` | in | digital, timed | FS/LS line levels: 10 = D+ high / D- low, 01 = D+ low / D- high, 00 = SE0. In the HS branch the same pins drive the HS switches statically (chirp K/J, termination calibration PD43) without the serializer or a PLL |
| `TX_OE` | in | digital, timed | output enable for `TX_DP/TX_DN`; 0 = high-Z (FS) / off (HS static path) |
| `HS_STR1`, `HS_STR0` | in | digital, static | new field `usbhs.config.drive_strength[1:0]`, reset 1. Strength of the HS gate driver (equivalent inverter 4/8, 6/12, 8/16, 10/20 um): trims the HS line edge rate against process (slow silicon 3, fast silicon 0) |
| `ISLAND_OFF` | in | `ISLAND_OFF_wired` (decode of `island_on[0]`, always-on domain) | 1 clamps all six outputs to VSS, also while the island supply ramps |
| `HS_PBIAS` | in/out | net `HS_PBIAS` (`hsbias.HS_PBIAS`, `pad_usb.HS_PBIAS`) | 20 pF bypass capacitor to this cell's VDD (PMOS gates); no DC current. The cell's VDD strap must join the pad's VDD at the pad HS sources (same rail, low impedance): a fast voltage difference between the two rails appears almost fully on the source gates (about 2 % of HS amplitude per 20 mV) |
| `HS_P`, `HS_N` | out | `pad_usb.HS_P`, `pad_usb.HS_N` | route as a matched pair, <= 1.5 mm, <= 150 ohm / 0.45 pF per wire (verified to that) |
| `FS_HIGH_P`, `FS_HIGH_N`, `FS_LOW_P`, `FS_LOW_N` | out | same-named `pad_usb` pins | break-before-make inside the cell |

Both static enables high at once is treated as "nothing selected" (all outputs low). Changing the branch while
`TX_OE` = 1 can leave `HS_x` and `FS_HIGH_x` of the same line both partly on for about 1 ns (same direction, no
shoot-through); change `HS_EN` / `FS_EN` only with `TX_OE` = `HS_DRV` = 0 (`rtl/pt_usb.sv` does).

Pins of `pt_wiredtx` itself: see `INTEGRATION.md` in this directory.

## `pad_usb` pins not driven by `pt_usb_txdrv`

| pad pin | connect to |
|---|---|
| `PAD_P`, `PAD_N` | chip-top `USB_DP`, `USB_DN` (PD22: `bidir[19]` / `bidir[18]`, bond 25 / 24) |
| `RX_P`, `RX_N` | nets `USB_RX_P/N` -> `rxselect.RX_P/N`, `detect.RX_P/N`, `wmon_sel.RX_P/N` (FR-4); **not** `ctle.RX` (MW-8) |
| `HS_PBIAS` | `hsbias.HS_PBIAS` and `usb_txdrv.HS_PBIAS` |
| `TERM_ENABLE`, `TERM_TRIM0..2` | `usbhs.config.term_enable`, `usbhs.config.term_trim` AND term_enable (DT-7) |
| `TERM_VCM`, `DIFF_ENABLE` | `termination.TERM_VCM`, `termination.DIFF_ENABLE`. **TERM_VCM must be at VSS (low impedance, about 2 ohm) in every USB mode, FS and LS included:** the pad's FS/LS low-side driver is the termination switch bank returning to TERM_VCM (qualified inside the pad by its `VCM_LOW_OK`), so with TERM_VCM at 1.2 V or floating the line cannot be driven low |
| `DIV_ENABLE`, `BYPASS_ENABLE` | `rxlevel.DIV_ENABLE`, `rxlevel.BYPASS_ENABLE` |
| `PULLUP_P`, `PULLUP_N`, `PULLDOWN_P`, `PULLDOWN_N` | `usbfs.config.pullup_p/n`, `pulldown_p/n` (register bits, wired island, reset 0) |
| `LS_SLOW` | `usbfs.config.ls_slow` (needs `usbhs.bias.enable` = 1, PD47) |
| `ATB_ESD_RAIL` | ATB leaf (INT-04, still missing) |

## Modes (register / signal settings)

| mode | static | timed |
|---|---|---|
| off / reset | everything 0 | - |
| FS device idle / attach | `PULLUP_P` = 1, `FS_EN` = 1 | `TX_OE` = 0 |
| FS transmit | as above | `TX_OE` = 1, `TX_DP/TX_DN` = NRZI line levels at 12 Mb/s, SE0 = 00 for EOP |
| LS (device) | `PULLUP_N` = 1, `FS_EN` = 1, `LS_SLOW` = 1, `usbhs.bias.enable` = 1 | as FS at 1.5 Mb/s |
| host | `PULLDOWN_P` = `PULLDOWN_N` = 1 | as FS / LS |
| chirp (device K, host K/J) | `HS_EN` = 1, bias on, `TERM_ENABLE` = 0 (device) | `TX_OE` = 1, `TX_DN` = 1 (K) or `TX_DP` = 1 (J) |
| HS idle / receive | `HS_EN` = 1, bias on, `TERM_ENABLE` = 1 + trim, termination mode 11, pull-up off, rxlevel bypass, `rxselect_direct` = 1 | `HS_DRV` = 0, `TX_OE` = 0 |
| HS transmit | as HS idle; `pt_wiredtx`: MODE_F (x4 repetition), `EN_MAIN` = 1, `EN_POST` = 0, MAIN / POST tail codes 0 (WIRE_TX pad silent) | `HS_DRV` = 1 for the packet; data words on D0..D39 |
| termination calibration (PD43) | `HS_EN` = 1, bias at half scale, `TERM_ENABLE` = 1 | `TX_OE` = 1, `TX_DP` = 1 (then `TX_DN`) |

## State of `pt_usb_txdrv` (netlist revision 3, 2026-11-14)

Revision 3 = strength-selectable HS gate driver, 20 pF HS_PBIAS bypass, break-before-make with direct interlock
and off-delay (after the independent review). 208 devices, 116.48 x 270.06 um = 31,457 um2, pins on the top edge.
Magic DRC 0, Netgen LVS unique, KLayout DRC 0, KLayout precheck (main + antenna) clean
(`generated/usbdrv-layout.json`, `usbdrv-lvs.txt`, `usbdrv-drc.txt`, `usbdrv-kldrc.json`). All numbers below are
from the extracted netlist `generated/usbdrv.ext.spice` with the extracted USB pad, the extracted bias DAC and the
COB package; limits and every job result are in `generated/usbdrv-evidence.json` (bench `sim_usbdrv.py`, raw runs
`scratch/wired_tx/usbdrv/runs/`). Results of revisions 1-2 are kept in `scratch/wired_tx/usbdrv/results-rev1/`
and are not evidence for this layout.

| check (limit) | tt 27/3.3 | ss 32/3.15 | ff 22/3.35 | sf / fs | ss pessimistic | ff fast |
|---|---|---|---|---|---|---|
| HS level, mV (360-440), calibrated bias code | 393 (code 100) | **351 FAIL** (code 0 = maximum; ss 22 C 356) | 395 (code 255 = minimum) | 394 / 393 | **350 FAIL** | 397 |
| HS template 1 inner / outer margin, mV (> 0) | 89 / 58 | 46 / 105 | 54 / 52 | 90 / 63, 88 / 56 | 46 / 109 | 94 / 50 |
| HS crossing jitter pk-pk, ps (inside template) | 78 | 42 | 186 | 78 / 85 | 149 | 71 |
| HS 10-90 % edge, ps (>= 500), strength code | 628-650 (1) | **490-538 FAIL** (3); 601-643 (2) | 857-873 (0) | 662-675 / 620-649 (1) | 722-787 (3); 872-942 (2) | 719-737 (0) |
| HS idle, mV (<= 10) | 0.2 | 0.2 | 0.2 | 0.2 | 0.5 | 0.2 |
| chirp K / J, V (0.5-0.9 / 0.7-1.1) | 0.79 / 0.78 | 0.69 / **0.68 FAIL** | 0.79 / 0.77 | 0.77 / 0.76, 0.81 / 0.80 | - | - |
| FS edges, ns (4-20) | 6.6-7.9 | 8.0-11.1 | 5.5-6.0 | 7.0-7.6 / 6.4-8.6 | 8.2-11.3 | 5.5-6.0 |
| FS crossover, V (1.3-2.0) | 1.68-1.74 | 1.53-1.61 | 1.79-1.84 | 1.76-1.81 / 1.61-1.68 | 1.50-1.58 | 1.79-1.84 |
| FS rise/fall matching (0.90-1.11) | **1.10-1.16 FAIL** | **1.28-1.33 FAIL** | 0.95-1.01 | 0.96-1.03 / **1.25-1.31 FAIL** | **1.27-1.34 FAIL** | 0.95-1.01 |
| ... same with an ideal driver (pad alone) | 1.10-1.15 | 1.28-1.32 | 0.95-1.00 | 0.97-1.02 / 1.25-1.30 | 1.27-1.32 | - |
| FS break-before-make gap, ns (0.2-6.0) | 4.0-4.1 | 5.1-5.2 | 3.3-3.4 | 3.9-4.0 / 4.1-4.2 | **6.4-6.6 FAIL** | 2.9-3.0 |
| FS gate overlap, V (< 0.5); pad VDD charge vs ideal (<= 1.10) | 0.19; 0.986 | 0.17; 0.982 | 0.21; 0.988 | 0.21; 0.987 / 0.18; 0.984 | 0.12; 0.975 | 0.26; 0.986 |
| input-skew / runt stress on the cell: overlap V (< 0.5), extra edges (0) | 0.005; 0 | 0.005; 0 | 0.007; 0 | 0.005; 0 | 0.004; 0 | 0.014; 0 |
| disabled: outputs V, cell IDD, pad leakage (0.05 V, 1 uA, 10 uA) | 0; 1.0 nA; 0.28 uA | 0; 1.0 nA; 0.26 uA | 0; 1.3 nA; 0.31 uA | 0; 1.0-1.2 nA; 0.28 uA | - | - |
| enable changes / ISLAND_OFF: quiet outputs V (<= 0.3) | 0.001 | 0.001 | 0.002 | 0.001 (sf, fs) | 0.001 | - |
| supply ramp 0-3.63 V, ISLAND_OFF high: outputs V (<= 0.3) | 0.0005 (27 C) | 0.0003 (0 C) | 0.0004 (85 C, 10 us); 0.004 (1 us) | - | - | - |
| CMD tap, fF (<= 25 incl. 15 fF route) | 10.1 (CMD_P), 9.3 (CMD_N) + 15 = **25.1 FAIL by 0.1** | 10.2 / 9.5 + 15 = **25.2 FAIL** | - | - | - | - |

HS strength codes per process (`STRENGTH` in the bench, fixed before the runs): tt/sf/fs 1, ss 3, ff 0. LS results:
edges 98-235 ns (limit 75-300) at tt 50 pF, ff 50 pF and ss 450 pF; crossover at 50 pF **2.02 V tt / 2.10 V ff FAIL** (limit 2.0 V; ideal-driver references `ref_ls_*` give 2.00 / 2.08 V, so pad-set); ss 450 pF 1.51-1.66 V.

Timing through the cell: `HS_DRV` high to line driven 1.7-3.3 ns, `HS_DRV` low to line idle 2.6-3.5 ns, data
`CMD` to line 1.3-2.0 ns (all corners, including the pessimistic set).

### What fails or is open (plain list)

1. **HS amplitude at ss (pad / bias limit, not this cell):** 350-356 mV in a packet, 355 mV DC with the bias DAC at
   its maximum; chirp J 0.68 V. Demand on pads (USB-D3) and on the DAC span (USB-D5).
2. **HS edge at ss with the declared strength code 3:** 482-490 ps minimum (limit 500 ps). Code 2 gives 601-643 ps
   at ss and 872-942 ps at ss pessimistic with template margin left (24 mV), so the ss rule should be code 2; the
   declared rule was not changed after the result. **There is no on-die observable that tells which code a die
   needs**: the code has to come from the bias-calibration code band or from a scope at bring-up.
3. **FS break-before-make gap at ss pessimistic 6.4-6.6 ns** against the 6 ns declared for this cell (not a USB
   limit; both lines shift equally, FS bit = 83 ns).
4. **CMD tap 25.1 fF** against the 25 fF declared (10.1 fF extracted + 15 fF assumed for 100 um of route).
5. **FS rise/fall matching** is the pad's known residual USB-01 (identical with an ideal driver, delta <= 0.023).
   LS crossover at 50 pF is likewise set by the pad (ideal driver: 2.00 V tt, 2.08 V ff against 2.0 V).
6. **Not simulated:** the clocked serializer (x4 mode) into this cell; the bench source is the real CMD_MAIN output
   stage (`wtx_nand2p1` + `wtx_nand2c`, schematic) with complementary inputs. The extracted `pt_wiredtx` was run
   through its external-data path only (`hs_ext_*_wtxext`): template 1 passes at tt, ff and ss (inner / outer
   margin 88 / 63, 25 / 52, 46 / 100 mV; 0 bit errors), with a wider edge spread (574-1006 ps) because that path
   has P/N skew on CMD_MAIN (one extra inverter in one leg). A 166-bit packet at tt (`hs_ext_tt_long`) gives the
   same level and margins as the 38-bit one (390 mV, 88 / 58 mV), so the bias node is settled.
7. **Not checked:** electromigration and wire widths of the HS gate driver outputs, oxide lifetime of the 20 pF
   PMOS-gate bypass at 3.63 V, ESD / CDM of inputs arriving from the digital domain, mismatch / Monte Carlo,
   negative controls for the off / mode / ramp / chirp / tap checks, pad-level run of the input-skew stress.
8. **Review:** one independent review of revision 2 found the break-before-make defeatable by inputs 0.8-3 ns
   apart (fixed in revision 3 and covered by the stress row above), a wrong chirp K limit and a level window that
   read 3-5 % low (both corrected, dated comments in `sim_usbdrv.py`), and the items listed here as open.
   Revision 3 has NOT been re-reviewed.
