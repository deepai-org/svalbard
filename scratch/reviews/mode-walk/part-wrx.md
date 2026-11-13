# Mode walk, part WRX: wired receive (low rate, top rate, USB, 100BASE-TX RX)

Reviewer scope: pad_hs_rx / pad_usb -> pt_termination / pt_rxlevel -> pt_ctle -> pt_rxselect -> pt_slicer -> pt_wrx_cap -> digital macro;
clock pt_pll_ring (pll_cdr) on pt_pll_vreg -> pt_ptrim -> slicer/capture; pt_cdr; pt_detect; pt_wmon_sel. Read-only review, 2026-11-13.

Paths are relative to `projects/programmable_transceiver_platform/` (`$P`) unless absolute. `IC` = `/home/ubuntu/svalbard/scratch/reviews/interface-changes.md`.
`BIND` = `/home/ubuntu/svalbard/scratch/integration/m6-powerup/chipnet/binding.json` (fresh chip netlist binding, v5 instance list).
Scripts, decks and logs for every number I produced: `/home/ubuntu/svalbard/scratch/reviews/mode-walk/wrx/`.

## What exists at chip level (verified)

* `integration/pt_chip.sv:119-147` `pt_analog_physical` is a blackbox. The only chip netlist is `verification/chip_assembly/netlist.py`.
* `BIND` has 147 instances. **Absent: `cdr`, `wrx_cap`, `ptrim`, `vthdac`, `pll_vreg`, `pll_tx`, a second `wordclk`.** `ptrim`, `vthdac`,
  `pll_vreg` have 0 occurrences in `inventory.py` and `netlist.py` (not masters, not instances). `cdr` and `wrx_cap` are masters
  (`inventory.py:62,71`) but are not in the v5 instance list the run used.
* Every control and clock pin of the wired RX cells is `UNBOUND_*` in `BIND` except: supplies, `ctle.IBIAS`, `detect.IBIAS`,
  `pll_cdr.IBIAS`, the five `EN_EFF_*` decodes (ctle, rxselect, slicer, detect, pll_cdr), `pll_cdr.REF/FBCK/BAND`, and the
  analog nets WRX_P/N, CTLE_P/N, SL_P/N, WMON_IN, TERM_ENABLE/DIFF_ENABLE/TERM_VCM, DIV_ENABLE/BYPASS_ENABLE.
* So almost every boundary below had to be judged from the two cells' own artefacts.

## Numbers produced in this review (cheap ngspice, tt unless stated)

| # | Question | Deck / script | Result |
|---|---|---|---|
| S1 | Pin capacitance of the CKP / SL nets from the published extracted netlists (gate area x 4.5 fF/um2 + overlap + extracted C lines; rough, +/-30 %) | `wrx/pincap.py` | slicer CKPk 179-218 fF; wrx_cap CKP0 ~ 231 (top wiring) + 445 (wc_front) + 92 (wc_pd) + 84 (wc_ctl) ~ 850 fF, CKP1..7 ~ 177 + 70..180 ~ 250-360 fF. Total per ring phase: **CKP0 ~ 1.0 pF, CKP1..7 ~ 0.45-0.6 pF** (no inter-block route). slicer SL_P/N ~ 0.66 pF each (283/301 fF of it is wiring, as README:1015 says). |
| S2 | pt_ptrim (schematic, code 16, 625 MHz, tt/27/3.3) with the bench load 150 fF vs the S1 loads | `wrx/ptrim_load.cir/.log` | 150 fF: delay 313 ps, 20-80 % rise 107 ps, full swing. Real loads: **CKP0 swings only 0.48-2.88 V, rise 638 ps (half period 800 ps), delay 559 ps; CKP1..7 delay 462 ps, rise 325 ps -> CKP0 lags the others by 96 ps = 21.6 deg at 625 MHz** (ptrim total range ~ 89 ps). PH swing 2.9 V / 150 ps edges (regulated ring rail) costs only +20 ps. Published `generated/ptrim.ext.spice` at 150 fF: toggles at 625 MHz tt, delay 581-611 ps (30 ps channel spread). |
| S3 | CTLE gain with the real receiver: extracted ctle -> extracted rxselect (CTLE branch) -> extracted slicer (+ wmon_sel off, 30 fF route) vs the block bench load 150 fF | `wrx/ctle_{0,3,7}_{bench,chain}.cir/.log` | code 0: 1.25 GHz gain **+2.1 dB (bench) -> -8.0 dB (chain)**, 625 MHz +3.8 -> -4.0 dB, -3 dB BW 1.82 GHz -> **248 MHz**. code 3: +2.4 -> -7.7 dB at 1.25 GHz. code 7: +2.6 -> -7.5 dB at 1.25 GHz, peak moves 631 -> 355 MHz and drops 4.4 -> -2.5 dB. |
| S4 | CTLE output common mode (extracted, op point, input CM 1.0 V) | `wrx/op_*.cir` (same deck, corner swapped) | tt/3.3 **1.47 V**; ss/3.15 **1.52 V**; ss/3.35 **1.66 V**; ff/3.15 1.21 V; ff/3.35 1.31 V. |
| S5 | pt_slicer (schematic, ss/32, 625 MHz quarter rate, 200 mVppd, pattern 1100 then 0011) at the S4 common modes | `wrx/mk_slicer.py`, `wrx/sl_sch_*.cir/.log` | All three cases decode correctly on all eight samplers: CM 1.00 V / 3.15 V (3.66 mA), CM 1.55 V / 3.15 V (3.10 mA), CM 1.66 V / 3.35 V (3.40 mA). Supply current drops 15 % at the high CM (tail headroom). Schematic only, 200 mVppd, a per-sampler-static pattern: a function check, not a sensitivity, aperture or extracted-speed check. |

## Boundary tables

Verdict OK needs both sides cited. MISMATCH = the two sides disagree or one side does not exist. UNVERIFIABLE = no artefact to compare.

### Mode 1 and 2: wired RX through the HS pair (480 Mb/s - 1.25 Gb/s, and 2.5 - 3.24 Gb/s quarter rate)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| pad_hs_rx.RX_P/N -> pt_ctle.RX_P/N | net exists | hspad pin list `analog/pads/generated/stress-safe-families/wired-receive-hs/physical.spice:6`; intended split `analog/wired_rx/README.md:792-793` (HS_RX -> ctle.RX only) | `verification/chip_assembly/netlist.py:96` binds `ctle.RX_P` to `WRX_P`, which is the USB pad's RX (`netlist.py:131-133`); `BIND` pad_hs_rx.RX_P = `UNBOUND_pad_hs_rx_RX_P` | **MISMATCH** | The serial RX pair reaches nothing in the chip netlist; the CTLE listens to the USB pins. Finding A1. |
| pt_termination HS_* -> pad_hs_rx TERM_*/VBIAS | pins, names, width | `analog/wired_rx/termination.spice:11` (HS_TERM_ENABLE, HS_TERM_TRIM0..3, HS_TERM_VCM, HS_VBIAS) | hspad `physical.spice:6` (TERM_ENABLE, TERM_TRIM0..3, TERM_VCM, VBIAS) | OK (cells) / **MISMATCH** (netlist) | 4-bit trim matches PD27 (`IC:806`). All seven nets `UNBOUND_*` in `BIND`. |
| register -> pt_termination hs_en / hs_term_en / hs_trim[3:0] | source, default | `termination.spice:6-8` (hs_en=0 grounds HS_VBIAS and HS_TERM_VCM; reset code 5 expected) | no field: `rtl/pt_regmap_defs.svh` has only TERMINATION_CONFIG__DIFFERENTIAL_100_ENABLE / P_LOAD (`:386`) and USBHS_CONFIG__TERM_TRIM 3 b (`:434`, USB pad) | **MISMATCH** | PD27 asked for `termination.config.trim[3:0]` reset 5 (`IC:806`); never implemented. With hs_en = 0 the CTLE input CM is 0 V. Finding A2. |
| HS pad VBIAS -> CTLE input CM | DC level | `termination.spice:6` HS_VBIAS 1.0 V divider (README:800: 0.95-1.01 V) | CTLE window 0.8-1.4 V tt, 0.8-1.2 V ss (`README.md:599-600`) | OK | Only when hs_en = 1. |
| CTLE IBIAS | direction, magnitude | `ctle.spice:97` NMOS pass into an NMOS diode; bench `sims.py:228` `RIB vdd ib 260k` (current into the pin, ~10 uA) | `integration/core_bias.py:18` wired bank consumer `ctle` (bank on RAIL_wired, `core_bias.py:121`); `BIND` ctle.IBIAS = BIAS_ctle | OK | |
| pt_ctle.CTLE_P/N -> pt_rxselect -> pt_slicer.SL_P/N (+ pt_wmon_sel) | load assumed vs real | CTLE bench load 150 fF per leg `sims.py:232-233`; eye qualification "150 fF slicer load per leg" `README.md:628` | slicer SL wiring alone 282.6 / 300.7 fF `README.md:1015`, plus gates, plus rxselect TGs `rxselect.spice:25-26`, plus wmon_sel `wmon_sel.spice:43-44` | **MISMATCH** | S3: -8 dB at 1.25 GHz instead of +2 dB; BW 248 MHz. Finding D2. |
| pt_ctle output CM -> pt_slicer input CM | DC level at corners | `ctle.spice:2` claims "output CM ~1.0 V"; README:601 says ~1.4 V; S4 measured 1.21-1.66 V | slicer range "0..~1.5 V" `slicer.spice:8`; every gating bench at CM 1.0 V `sims.py:446,455` (`generated/slicer-evidence.json` cases `*_cm1_*`) | **MISMATCH** | Finding D1. The same CM is where the rxselect TG is weakest (both devices near threshold), which is part of D2. |
| rxselect control | field / encoding | `rxselect.spice:6` rxselect_en, rxselect_direct | `pt_regmap_defs.svh:372` RXSELECT_SELECT__BRANCH (1 b), EN_EFF_rxselect `rtl/pt_digital_macro.sv:185` | OK | `rxselect_direct` itself is `UNBOUND` in `BIND`. |
| ctle control | width | `ctle.spice:13` ctle_peak0..2, lf_zero0..2, wire_ctle_bypass | `pt_regmap_defs.svh:268` CTLE_CONFIG__ZERO_TRIM, 2 bits on the bus (register-map.json `bus_bits` 2); no lf_zero field; bypass = `:50` DEBUG_WIRE_BYPASS__CTLE | **MISMATCH** | Peak codes 4-7 (the >= 12 dB settings) unreachable; lf_zero has no source (`IC:785` asked for `ctle.config.lf_zero[2:0]`). |
| pt_pll_ring supply | domain | ring verified on the regulator output, 2.69-3.015 V: `analog/timing/pll_ring.spice:4`, `README.md:829` | `BIND` pll_cdr.VDD = RAIL_pll; `pll_vreg` not in `inventory.py`/`netlist.py` (0 hits); macro gates the enable on `vreg_rx_ok` `rtl/pt_digital_macro.sv:175-177` | **MISMATCH** | Ring range / Kvco / phase spacing evidence is for a rail the netlist does not create. Finding D5. |
| pll_cdr.PH0..7 -> pt_ptrim.PH0..7 | pins, order | `pll_ring.spice:37` PH0..PH7 | `ptrim.spice:7` PH0..7 -> CKP0..7 straight | OK (cells) | `ptrim` is not in the chip netlist at all; `BIND` PH0..7 `UNBOUND`. |
| ring phase swing -> ptrim NAND (3.3 V) | level | ring rail ~0.9 x VDD (`pll_ring.spice:4`) | ptrim bench drives PH at full VDD, 60 ps edges `sims.py:717` | OK (S2: +20 ps at tt with 2.9 V / 150 ps) | Corners not simulated. |
| pt_ptrim.CKP0..7 -> pt_slicer + pt_wrx_cap | load, swing, skew | ptrim bench load 150 fF "slicer + capture clock pins and route" `sims.py:706-707,718` | S1: ~1.0 pF (CKP0), ~0.45-0.6 pF (CKP1..7). Slicer and capture benches use ideal full-swing clocks: `generated/slicer-evidence.json` excluded_coverage[2]; `capture.py:648` | **MISMATCH** | S2. Finding A5. |
| ptrim layout | usable cell | `README.md:389-390` generic row layout "290,000 um2 and not symmetric ... not usable as laid out"; `README.md:852` "published ptrim.ext.spice does not toggle" | `generated/ptrim.ext.spice:3` is that layout; no `ptrim-evidence.json` | **MISMATCH** | Part of A5. |
| ptrim trim bits | field | `ptrim.spice:3` T{k}_4..0 = cdr.phase_trim[k] | `pt_regmap_defs.svh:454` CDR_PHASE_TRIM__P0..P7, 5 b each, reset 0 | OK | Field is on the pll island, the cell on VDD_WIRE_SW; unbound in `BIND`. |
| ptrim_en | source | `ptrim.spice:4` | `rtl/pt_digital_macro.sv:49,128` `wire_rx_ptrim_en` | OK (cells) / **MISMATCH** (top) | The output is not connected in `integration/pt_chip.sv` (no occurrence). |
| CKPk -> sampler -> S_j order | phase order | `slicer.spice:4` D0@CKP0, E0@CKP1, D1@CKP2 ... E3@CKP7 | `capture.py:7-13` S_j = sampler at phase j, quarter DLj = O(2j), ELj = O(2j+1) | OK | Slicer pins are named D0,E0,..; capture pins S0..S7: binding S0=D0, S1=E0, S2=D1 ... must be written somewhere; `BIND` has D/E `UNBOUND`. |
| ring PH order vs CKP order | closed-loop evidence | `sims.py:1237` ring PHk wired to slicer CKPk, loop locks (`README.md:1251`) | same | OK | Without ptrim and without the capture load. |
| slicer D/E -> wrx_cap S | level, timing | both on VDD_WIRE_SW (`slicer.spice:11`); output valid one period (`slicer.spice:6`) | `capture.py:7-9` re-capture on CKP(j+4), RCS select `capture.py:319-329` | OK | Field `cdr.config.cap_rcsel`, RCS = bit 1 (`pt_regmap_defs.svh:210`). |
| slicer.QCK | consumer | `slicer.spice:7` "for the RTL" | capture uses CKP0 directly (`capture.py:5`) | OK (unused pin) | Cosmetic. |
| wrx_cap rate mode B2/B1, PSEL0..2, SLIPP/SLIPM, EN | source | `capture.py:570-571`, `generated/wrx_cap.lvs.spice:4707` | no field, no macro port: `rtl/pt_digital_macro.sv:25-75`; no `psel`/`slip` anywhere in `rtl/` | **MISMATCH** | Finding A3. |
| wrx_cap.LDE | source, frequency relation | needs one pulse per 20-bit word; slot chain has no wrap-around `capture.py:210-211`; bench pulses LDE every word `capture.py:655-661` | single `pt_wordclk` instance (`inventory.py:293`), "shared ... for wired TX and RX" `analog/timing/wordclk.spice:2`, its WORD_CLK is the TX net `netlist.py:114`, CK/LDE `UNBOUND` in `BIND` | **MISMATCH** | RX ring and TX ring are different clocks. Finding A4. |
| wrx_cap UP/DN -> pt_cdr UP/DN and pll_cdr FU/FD | pins, pulse width | `capture.py:434-441` one ring cycle per vote, 4 legs | `cdr.spice:22` UP0..3/DN0..3; `pll_ring.spice:11-15,37` FU0..3/FD0..3 one ring cycle each | OK (cells) | All `UNBOUND` in `BIND`; crosses wired -> pll island with no iso cell defined. |
| pt_cdr.VCTRL -> pll_cdr | pin | `cdr.spice:22` VCTRL | ring has no VCTRL pin; the loop node is `ATB_VCTRL` `pll_ring.spice:64,89-90` | OK (by design) / **MISMATCH** (netlist) | `netlist.py:122` binds cdr.VCTRL to a net `CDR_VCTRL` that nothing else is on; `BIND` pll_cdr.ATB_VCTRL `UNBOUND`. |
| pt_cdr pins vs netlist.py | stale bindings | `cdr.spice:22` (no FBCK_IN, no freq_hold; removed by AC3-W1, `IC:430`) | `netlist.py:122` binds `cdr.FBCK_IN`, `cdr.freq_hold` | **MISMATCH** | Also pll_cdr.REF should be cdr.REF_PLL (`IC:968`), HOLD should be cdr.HOLD_PLL. |
| pt_cdr.IBIAS / IB_PLL | bias source | `cdr.spice:51` IBIAS in; `cdr.spice:58` IB_PLL out ("10 uA bias for the PLL charge pump", `cdr.spice:19`) | `core_bias.py:17` pll consumers: pll_ring_tx, pll_ring_rx, pll_ring_host, lc_vco_reserved (no cdr); `netlist.py:24` maps pll_cdr -> pll_ring_rx | **MISMATCH** | No bias output for pt_cdr; ring IBIAS has two candidate sources. Finding D4. |
| pt_cdr source vs layout | revision | `cdr.spice:22` r12 with otr0..4, otrs | `generated/cdr.lvs.spice:3`, `generated/cdr.ext.spice:3` (26 pins, r11 per `generated/cdr-evidence.json`) | **MISMATCH** | Offset trim not in the layout and no register field. |
| CDR frequency acquisition | who drives FUP/FDN | `cdr.spice:6-7` FLL (FUP/FDN) needed; `IC:287` "RTL FLL drives ..."; closed-loop benches preset VCTRL "stands in for the FLL result" `sims.py:1212`; P path alone fails at +3000 ppm `README.md:1244-1245` | hardened RTL has no FLL: only `cdr_freq_locked` level `rtl/pt_digital.sv:24,78`; `analog/wired_rx/rtl/pt_wrx_cdr_loop.sv` is not instantiated in `rtl/` and still speaks freq_hold / bb_up (`pt_wrx_cdr_loop.sv:12-13`) | **MISMATCH** | Finding A3. |
| pt_cdr / ring static controls (pfd_mode, ref_sel, g0..2, KP0..2, N4/N8/N5/N10, BAND) | fields | `cdr.spice:22`; `pll_ring.spice:37` | g <- `pt_regmap_defs.svh:450` CDR_AC3__LOOP_BW (3 b); N4/N8 <- `:98` CONSOLIDATION_PLL__FEEDBACK_N (2 b, debug bus); no field for pfd_mode, ref_sel (`CDR_AC3__FLL_REF_WCK` `:452` is the nearest), KP (`IC:452` asked `cdr.config.kp[2:0]`), N5/N10; BAND tied to VDD `netlist.py:121` | **MISMATCH** | KP = 0 means "path off" (`pll_ring.spice:15`): no proportional path without the field. |
| FBCK -> frequency counter | ratio, rate | ring feedback /16 (or /10 with N5/N10) `pll_ring.spice:19-20,8` -> <= 52 MHz (83 MHz in /10) | `integration/pt_digital_macro.sdc:27-28` fc clocks constrained at 156.25 MHz; `BIND` pll_cdr.FBCK = fc_src[1] | OK | |
| wrx_cap DX[39:0], WCLK40 -> macro | pins exist, order | published cell `generated/wrx_cap.lvs.spice:4707` (DX0..39, WCLK40); `README.md:377-378` DX = {later, earlier word}, sample on WCLK40 rise | `rtl/pt_digital_macro.sv:37-39`, `rtl/pt_digital.sv:11` | OK (published r6) | Source `capture.py:530-531,570-574` is r7 (DW/EW/WSTB, gear removed, W7-GEAR `IC:1043`): publishing it breaks this boundary until the macro front end exists. Finding D7. |
| wire_rx_clk period | SDC | line/40: 12.3 ns at 3.24 Gb/s | `integration/pt_digital_macro.sdc:20-22,30,85` WRX_PERIOD 12.3 | OK | |
| DX vs WCLK40 timing | setup/hold | "DX changes while WCLK40 is high" `README.md:378`; no min/max number in `generated/wrx_cap-evidence.json` | `pt_digital_macro.sdc:293,296` one input delay 0.2 x period for min and max | UNVERIFIABLE | Hold at the macro depends on an unpublished clk->DX minimum. |
| wire_rx_valid | producer | none: `generated/wrx_cap.lvs.spice:4707` has no valid pin | `rtl/pt_core.sv:87` ingress gated on wire_rx_valid | **MISMATCH** | Dangling in `BIND`. |
| wire_analog_status (cdr_qualified, cdr_loss, rx_state, slicer_data/early/late, electrical_quiet) | producer | none of pt_cdr / pt_slicer / pt_detect has such outputs (`cdr.spice:22`, `detect.spice:11`) | `rtl/pt_digital.sv:41-46` | **MISMATCH** | Also no consumer for `cdr.config.acquisition_timeout_ui`, `holdover_bits`, `loop_gain_code`, `loss_arm`, `quiet_source`, `scheduled_quiet_limit_ui`, `periodic_tracking_enable`, `phase_trim` (legacy 5 b). |
| slicer offset trim | width | `slicer.spice:11` 8 samplers x (p0-2, n0-2, f0-3) = 80 pins | `pt_regmap_defs.svh:376` SLICER_OFFSET__DATA/EARLY/LATE, 4 b each | **MISMATCH** | Reset (all 0) is safe. 60 mVppd result needs p0 on each sampler (`sims.py:312-314`). Finding D6. |
| capture evidence | covers the published cell | `generated/wrx_cap-evidence.json`: tests.safe = fail, clean = fail, only `*_q625` benches, written 2026-11-10 | `generated/wrx_cap.lvs.spice` written 2026-11-11 | **MISMATCH** | No 810/834 MHz, half or full rate, or corner record in the published evidence file. |
| top rate 2.7-3.24 Gb/s | sampler at 810 MHz | `generated/slicer-evidence.json` perf[0]: 0 errors at 810 MHz, 2 of 12 corners, ideal clocks | `IC:1054` (R8-ARCH): "broken 810 case 19/30", eighth-rate mode "Proposed, not implemented"; `IC:224` (WT21) caps the ring at 625 MHz | **MISMATCH** | Finding D3. |
| pt_detect on the HS pair | squelch / LOS | `README.md:804-808`: detect cannot take the HS pair or the CTLE output | route is IX-10 + IX-12 (not implemented, see mode 4) | **MISMATCH** | No signal detect for the serial pair. |
| island crossings (PH pll->wired, UP/DN wired->pll, DX wired->core) | iso / level cells | `IC:420` (RA-2): v3 has no iso_clamp instances | `BIND` has ISO_wired / ISO_pll nets only on the switches | UNVERIFIABLE | Gate-only inputs in each case; not traced further. |

### Mode 3: USB (pad_usb pair)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| chip top USB pins | exist | bond map `spec/contract.json:80-81` (HS pair on bidir[14]/[15]); PD22 `IC:801` USB_DN/USB_DP on bidir[18]/[19] | `integration/pt_chip.sv:11-21` has no USB_DP/USB_DN port, still has WCLK_OBS/WDBG_OBS; `pt_chip.sv:1` "USB control/data macros remain unimplemented" | **MISMATCH** | |
| pad_usb.RX_P/N -> rxselect.RX, detect.RX, wmon_sel.RX | net | `README.md:792` | `netlist.py:96-100,131-133` (WRX_P/N) | OK | And wrongly also to ctle.RX (see A1). |
| HS RX: pad -> rxselect direct -> slicer | CM, swing | USB HS CM ~0.2 V, 400 mV `README.md:810-814` (SL CM 0.20-0.22 V) | slicer bench `ring480M_usbhs_0.48G_cm0.2_400mVpp` 0 errors (`generated/slicer-evidence.json` perf[5]) | OK | |
| HS RX clocking | full-rate sampling phase | capture full rate: PD off, "blind phase picker" `capture.py:438-439`; psel/slip come from RTL `analog/wired_rx/rtl/pt_wrx_cdr_loop.sv:22-31` | not instantiated; no PSEL/SLIP port on the macro | **MISMATCH** | Finding A3. |
| HS termination | encoding | `termination.spice:3-4` term_mode 00 off, 01 TERM_VCM 1.2 V, 10 100 ohm diff, 11 VSS (USB HS) | register-map `termination.config.p_load` values off / 45_to_ground / 50_to_vcm (`pt_regmap_defs.svh:386`) + `differential_100_enable`; no `term_en` source | **MISMATCH** | A raw bit binding makes "45_to_ground" (1) select the 1.2 V shunt. Needs a decode that exists nowhere. Finding D8. |
| HS termination trim | width | pad `.../wired-receive-usb/physical.spice:1` TERM_TRIM0..2 | `pt_regmap_defs.svh:434` USBHS_CONFIG__TERM_TRIM 3 b, reset 4, gate_and | OK | `UNBOUND` in `BIND`. DC value 39.6-53.3 ohm at ff/ss, outside 45 +/-10 % (`README.md:812-813`). |
| HS TX data -> pad HS_P/HS_N | driver | pad pins HS_P, HS_N `physical.spice:1` | pt_wiredtx has only CMD_MAIN/POST to txpad (`analog/wired_tx/wiredtx.spice:1124`); no macro port | **MISMATCH** | "USB HS through pt_wiredtx ... is not simulated" `analog/wired_tx/README.md:242-243`. Finding A6. |
| HS bias | field, pins | `analog/wired_tx/hsbias.spice:8` EN, C0..7, HS_PBIAS | `pt_regmap_defs.svh:426` USBHS_BIAS__CODE; `BIND` hsbias.C0..7 = analog_cfg[478..485], EN = [486], HS_PBIAS net to pad | OK | hsbias.IBIAS is bound to an ATB node name (`ATBN_usbhs_ibias`), not to a core_bias output (core_bias.py:18 has no hsbias consumer): not traced further (TX reviewer). |
| FS/LS driver FS_HIGH_P/N, FS_LOW_P/N | driver | pad pins `physical.spice:1` | none: no block, no macro port; only static `usbfs.config.drive_enable` (`pt_regmap_defs.svh` USBFS_CONFIG) | **MISMATCH** | Finding A6. |
| pull-ups / pull-downs, LS_SLOW | fields, reset | pad pins PULLUP_P/N, PULLDOWN_P/N, LS_SLOW | `pt_regmap_defs.svh:418` USBFS_CONFIG__PULLUP_P etc., all reset 0 (register-map.json) | OK | `UNBOUND` in `BIND`; usbfs fields have `islands: []` while the pad is on the wired rail. |
| FS/LS receive, SE0, squelch, disconnect | consumer of detect outputs | `detect.spice:3-4,11` DIFF_POS, DIFF_NEG, SE_P, SE_N ("SE0 ... in RTL") | no RTL; `wire_status` bits usb_squelch / detect_event have no producer (`rtl/pt_digital.sv:41-46`) | **MISMATCH** | Thresholds exist (`detect.spice:8`: 125 mV squelch, ~555 mV disconnect code, 0.8/2.0 V SE). |
| detect thresholds | field width | `detect.spice:11` det_thr0/1, det_se0/1 | `pt_regmap_defs.svh:290-291` LOW_THRESHOLD_CODE 2 b; HIGH_THRESHOLD_CODE 2 b | OK | Names differ; `usbhs.config.squelch_code/disconnect_code` are dropped fields. |
| detect.det_clk | source | `detect.spice:2` | macro `ct_det_clk` (`rtl/pt_digital_macro.sv:69`); `pt_chip.sv:82` ties `ct_cfg_det_div` to 0 and the enable to CLOCKTREE_CONFIG TX_ENABLE | UNVERIFIABLE | `UNBOUND` in `BIND`. |
| rxlevel | encoding | `rxlevel.spice:7` rxlevel_en, rxlevel_half | `pt_regmap_defs.svh:366` RXLEVEL_CONFIG__PATH values off / bypass / half | **MISMATCH** | Needs decode (en = path != 0, half = path[1]). Raw binding makes "half" = disabled. |
| pad state at reset | no pull-up, no drive | every usbfs/usbhs/usbdrive field resets to 0 (register-map.json defaults) | pad control pins are gate inputs `physical.spice:1` | UNVERIFIABLE | All pad control pins `UNBOUND` in `BIND`, so the reset level at the pad is undefined in the netlist. |

### Mode 4: 100BASE-TX receive (IX-9 .. IX-13)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| pt_vthdac -> pt_slicer VTAP/VTAN/VTBP/VTBN | pins, levels | `vthdac.spice:5,8` CM ~0.8 V, +/-1.6 V diff FS | `slicer.spice:11`; slicer bench default 0.8 V `sims.py:299` | OK (cells) | `vthdac` not in inventory/netlist; `BIND` slicer.VT* `UNBOUND`. |
| vthdac A[7:0], B[7:0], vth_en; slicer vsel_e*[1:0] | fields | `vthdac.spice:8`; `slicer.spice:11` | none in `pt_regmap_defs.svh` (`IC:982` asked for `cdr.vth_a/b[7:0]`, `cdr.vth_sel_e0..e3`, `cdr.vth_en`) | **MISMATCH** | Reset state safe (aux pairs off). |
| fast threshold update (IX-11) | H2D opcode | `IC:783` | only opcode 4 (RF fast gain) exists: `rtl/pt_core.sv:270-279`, `rtl/pt_quad_link.sv:165` | **MISMATCH** | No baseline-wander loop; the HS pad's on-die AC coupling has a 0.67-1.07 MHz high-pass (`IC:800`). |
| raw dual-lane capture (IX-12) | edge word to the host | capture exports EW only as cell pins; published cell gears DW only into DX (`README.md:377`) | macro "has no edge-sample input today (DX = data only)" `IC:1055`; no `psel_force` / `cfg_raw` field | **MISMATCH** | The FPGA cannot get the second (threshold) lane. |
| CTLE LF zero (IX-13) | field | `ctle.spice:8-12` lf_zero[2:0], effective at peak code 7 | no lf_zero field; peak code limited to 0..3 (`pt_regmap_defs.svh:268`, 2 bits) | **MISMATCH** | |
| rate | ring / mode | 125 MBd, ring 750 MHz = 6x, full-rate mode (`IC:784`) | needs B1 = 1 (full) and a fixed odd psel: no source (A3) | **MISMATCH** | |
| RX needs from TX (other reviewer) | MLT-3 levels | `IC:781` POST polarity bit `wiredtx.config.post_polarity` | pt_wiredtx has pin POST_POL (`wiredtx.spice:1124`); no such field in `pt_regmap_defs.svh` | **MISMATCH** | Needed for an MLT-3 loopback/peer test of the RX path. |

## Findings, ranked

### DEAD MODE

**A1. The HS receive pair is not connected to the receiver in the chip netlist; the CTLE is wired to the USB pins (modes 1, 2, 4).**
`netlist.py:96` binds `ctle.RX_P/N` to `WRX_P/N`, and `netlist.py:131-133` gives that net to the wirepad (USB) RX. `BIND` shows
`pad_hs_rx.RX_P/RX_N/VBIAS/TERM_VCM/TERM_ENABLE/TERM_TRIM0..3` and `termination.HS_*` all `UNBOUND_*`. The wired RX owner's
own decision (`analog/wired_rx/README.md:788-794`) is USB_RX -> rxselect/detect/wmon_sel and HS_RX -> ctle only. Reproduce:
`python3 -c "import json;b=json.load(open('<BIND>'));print(b['bindings']['pad_hs_rx'], b['bindings']['ctle'])"`.
Owner: chip assembly (`netlist.py` PATHS / PAD_PORTS: add an `hspad` family entry and the HS_RX_P/N net).

**A2. No register drives the HS pad bias and termination (modes 1, 2, 4).** `pt_termination` needs `hs_en`, `hs_term_en`,
`hs_trim[3:0]` (`termination.spice:6-8,11`); with `hs_en = 0` it grounds `HS_VBIAS` and `HS_TERM_VCM`, so the CTLE input sits at 0 V
(CTLE window starts at ~0.8 V, `README.md:599-600`) and the pair is unterminated. The register map has no such field
(`grep -n TERMINATION rtl/pt_regmap_defs.svh` -> only DIFFERENTIAL_100_ENABLE and P_LOAD; PD27 `IC:806` asked for
`termination.config.trim[3:0]` reset 5). `term_en` has no source either. Owner: digital (register map), wired RX (confirm reset code).

**A3. The CDR control plane does not exist in the hardened digital (modes 1, 2, USB HS RX, 4).** The analog side expects from RTL:
FLL pulses `FUP/FDN` (`cdr.spice:6-7`, `IC:287,430`), `pfd_mode`, `ref_sel`, `KP[2:0]`, `N5/N10`, capture rate mode `B2/B1`,
full-rate `PSEL[2:0]` / `SLIPP` / `SLIPM`, capture `EN`. The macro port list (`rtl/pt_digital_macro.sv:25-75`) has none of them and
no register field for them; the only CDR output is the level `cdr_freq_locked`. `analog/wired_rx/rtl/pt_wrx_cdr_loop.sv` (FLL,
phase picker, slip) is not instantiated under `rtl/` (`grep -rn pt_wrx_cdr_loop rtl/ integration/` -> nothing) and is written
against the retired `freq_hold / bb_up / bb_dn / bb_gain` pins (`pt_wrx_cdr_loop.sv:12-13`). The loop cannot acquire without the
FLL: the P path alone fails at +3000 ppm (`README.md:1244-1245`), the model "acquisition" assumed the FLL (`README.md:1247`), and
every closed-loop bench presets VCTRL (`sims.py:1212`, `.ic v(vctrl)`). With `KP` unbound/0 the proportional path is off
(`pll_ring.spice:15`). Full-rate modes (480-786 Mb/s, USB HS, 100BASE-TX) have no phase detector in the analog at all
(`capture.py:438-439`). Owner: digital (new RX front end in the macro + fields), wired RX (re-target `pt_wrx_cdr_loop.sv` to the
r12 `pt_cdr` pins), coordinator (decide where the FLL lives).

**A4. The capture has no word-restart (LDE) source (all wired RX modes).** `pt_wrx_cap` produces a word only when `LDE` pulses once
per 20 bits; the slot chain "has no wrap-around: every word is seeded by INJ" (`capture.py:210-211`; bench `capture.py:655-661`).
LDE comes from `pt_wordclk` clocked by the same ring phase as the capture (`analog/timing/wordclk.spice:3,14-15`). There is one
`pt_wordclk` instance (`inventory.py:293`), described as shared by TX and RX (`wordclk.spice:2`), with `WORD_CLK` on the TX net
`ct_word_clk` (`netlist.py:114`, which the macro also drives as an output, `rtl/pt_digital_macro.sv:68`) and `CK`, `EN`, `D10`,
`D20`, `LDE` `UNBOUND` in `BIND`. The RX ring (pll_cdr, recovered) and the TX ring (pll_tx) are different frequencies, so one
divider cannot serve both; and `D10/D20` (rate) have no field. Owner: timing / assembly (second `pt_wordclk` on pll_cdr CKP0), digital (rate field).

**A5. No verified clock path from the ring to the eight samplers and the capture (all wired RX modes; worst at >= 625 MHz).**
(a) `pt_ptrim` is in neither `inventory.py` nor `netlist.py`. (b) Its published layout is the generic-row one the owner calls "not
usable as laid out" (`README.md:389-390`) and "does not toggle" (`README.md:852`); there is no ptrim evidence file. (c) Its bench
load is 150 fF per phase (`sims.py:718`), but the published extracted slicer + capture present ~1.0 pF on CKP0 and ~0.45-0.6 pF
on CKP1..7 (S1). With those loads the schematic ptrim at 625 MHz tt gives CKP0 0.48-2.88 V with a 638 ps rise and a 96 ps
(21.6 deg) lag against the other phases, more than the ~89 ps trim range (S2). (d) The slicer and the capture were qualified only
with ideal full-rail 40-60 ps clocks (`generated/slicer-evidence.json` excluded_coverage[2]; `capture.py:648`), and the extracted
closed loop wires ring PH straight to the slicer with no ptrim and no capture (`sims.py:1237`). Reproduce:
`cd /home/ubuntu/svalbard/scratch/reviews/mode-walk/wrx && ngspice -b ptrim_load.cir` (rows `*_b0` vs `*_b1`); loads from
`python3 pincap.py <ext.spice> <subckt> CKP0,CKP1`. Caveat: S1 is a gate-area + extracted-C estimate; the CKP0 number is dominated
by `wc_front` (445 fF), which should be confirmed with an AC measurement. Owner: wired RX (ptrim compact layout, CKP0 buffer
split in the capture, re-bench slicer/capture from real ptrim outputs), assembly (place it).

**A6. USB has no data path in either direction through the chip (mode 3, all speeds).** Pad pins `HS_P/HS_N` and
`FS_HIGH_P/N`, `FS_LOW_P/N` (`.../wired-receive-usb/physical.spice:1`) have no driver: `pt_wiredtx` only has `CMD_MAIN/POST`
to the txpad (`analog/wired_tx/wiredtx.spice:1124`), the macro has no USB port or logic (`grep -il usb rtl/*.sv` -> nothing;
`integration/pt_chip.sv:1`), and the chip top has no `USB_DP/USB_DN` (`pt_chip.sv:11-21`). On the receive side `pt_detect`'s
SE_P/SE_N/DIFF outputs have no consumer and the status bits `usb_squelch`, `detect_event` no producer. HS receive data could use
slicer -> capture in full rate, but that needs A3 (phase picker) and A4. Static pieces that do exist and match: pull-up/pull-down
/ls_slow fields, 3-bit term trim, hsbias code. Owner: coordinator (USB is in scope per the mandate; decide FPGA-driven pins vs
on-die logic), then digital, pads, wired TX.

**A7. 100BASE-TX receive has none of its digital half (mode 4).** No fields for `vthdac` A/B/vth_en or slicer `vsel_e*`; no IX-11
opcode (`rtl/pt_core.sv:270-279` handles opcode 4 only); the macro takes no edge word (`IC:1055`); no `psel_force`/raw mode; CTLE
`lf_zero` has no field and peak code 7 is unreachable; `vthdac` is not in the inventory. The analog cells (slicer r7 aux pairs,
vthdac, CTLE r3) agree with each other. Owner: digital.

### DEGRADED

**D1. CTLE output common mode is 1.2-1.66 V, the slicer was qualified at 1.0 V.** `ctle.spice:2` says ~1.0 V; the extracted cell
gives 1.47 V (tt), 1.52 V (ss/3.15), 1.66 V (ss/3.35) (S4; `README.md:601` says ~1.4 V). The slicer header gives 0..~1.5 V
(`slicer.spice:8`) and every gating bench uses CM 1.0 V (`sims.py:455`). Only a tt "CTLE-driven" run exists (`README.md:985`).
A schematic function check at ss with 200 mVppd passes at CM 1.55 and 1.66 V (S5), with 15 % less sampler current, so this is an unqualified operating point rather than a shown failure; sensitivity and the 810 MHz margin at that CM are unknown, and D2 leaves far less than 200 mVppd there. Owner: wired RX (lower the CTLE load resistance / tail current, or qualify the slicer at 1.2-1.7 V at ss).

**D2. CTLE bandwidth collapses with its real load.** Bench and eye qualification use 150 fF per leg (`sims.py:232-233`,
`README.md:628`); the real load is rxselect's TG (weak at this CM) + ~0.66 pF of slicer + wmon_sel. Extracted chain, tt: -8.0 dB
at 1.25 GHz (bench +2.1 dB), -4.0 dB at 625 MHz (bench +3.8 dB), -3 dB at 248 MHz (S3). Peaking code 7 does not recover it
(-7.5 dB). This is a 10 dB loss at Nyquist for 2.5 Gb/s and 6-8 dB for 1.25 Gb/s, before any channel loss; 200 mVppd at the pad
becomes ~80 mVppd at the samplers at 2.5 Gb/s (the slicer's 60 mVppd point needs per-sampler trim, D6). Reproduce:
`ngspice -b ctle_0_chain.cir` vs `ctle_0_bench.cir` in the `wrx/` directory. This may well be a dead mode 2; I rank it here only
because the tt CTLE-driven slicer run at 625 MHz reports 0/68 (`README.md:985`; whether rxselect was in that bench is not stated).
Owner: wired RX (CTLE output stage / rxselect TG sizing or CM, or drive the slicer directly).

**D3. No passing evidence chain above 2.5 Gb/s.** The published quarter-rate slicer has a "broken 810 case 19/30" and the
eighth-rate replacement is "Proposed, not implemented" (`IC:1054`); the 810 MHz slicer rows cover 2 of 12 corners with ideal
clocks; the published capture evidence has only 625 MHz quarter-rate benches and reports safe = fail / clean = fail
(`generated/wrx_cap-evidence.json`); A5 and D2 get worse with rate. Owner: coordinator (state 2.5 Gb/s as the RX top rate or fund R8-ARCH).

**D4. pt_cdr has no bias output and the netlist bindings for it are stale.** `core_bias.py:17` has no `cdr` consumer and
`netlist.py:24` no map entry, so `cdr.IBIAS` would be unbound; `cdr.IB_PLL` (`cdr.spice:58`) is meant for the ring's IBIAS, which
the netlist feeds from `BIAS_pll_ring_rx` instead. `netlist.py:122` binds pins that no longer exist (`FBCK_IN`, `freq_hold`),
puts `cdr.VCTRL` on a net nothing else joins (ring side is `ATB_VCTRL`), leaves `HOLD`, `FU/FD`, `KP` unbound, and feeds
`pll_cdr.REF` from `ref_clk` instead of `cdr.REF_PLL` (`IC:968` lists this as still to wire). The spare `pll_ring_host` bank
output exists since pll_host was deleted. Owner: assembly.

**D5. The CDR ring is verified on a regulator the chip netlist does not contain.** `pll_ring.spice:4` (2.69-3.015 V), macro
`vreg_rx_ok` gating (`rtl/pt_digital_macro.sv:175-177`), but `pll_vreg` is absent from `inventory.py`/`netlist.py` and
`BIND` puts `pll_cdr.VDD` on `RAIL_pll`. Range (393-834 MHz), Kvco and ppm/vote numbers do not apply to that connection.
Owner: assembly / pll_vreg owner.

**D6. Slicer per-sampler trim cannot be programmed.** 80 trim pins and 8 vsel pins against 12 register bits
(`pt_regmap_defs.svh:376`). The extracted systematic offset is -15 mV at code p0 and the 60 mVppd point is "trimmed"
(`generated/slicer-evidence.json` perf[6], perf[8]). Owner: digital (per-sampler fields), wired RX (bit map).

**D7. Capture source is ahead of the published cell and of the macro.** `capture.py:530-531,570-574` (r7: DW/EW/WSTB, no gear)
vs `generated/wrx_cap.lvs.spice:4707` (r6: DX/WCLK40) vs the macro (DX/WCLK40, `rtl/pt_digital_macro.sv:37-39`). Today's published
pair is consistent; a rebuild of `generated/` from the source breaks the boundary, and the edge re-time stage the slicer owner
requires (SLI7-M, `IC:1041`) exists in neither. Also `pt_cdr` source r12 (otr pins, `cdr.spice:22`) vs layout r11
(`generated/cdr.lvs.spice:3`). Owner: wired RX / capture fork, digital.

**D8. Register encodings that need a decode nobody owns.** `termination.config.p_load` (off / 45_to_ground / 50_to_vcm) and
`differential_100_enable` vs `term_en`, `term_mode[1:0]` (`termination.spice:3-4`); `rxlevel.config.path` (off / bypass / half) vs
`rxlevel_en`, `rxlevel_half`; `debug.wmon_select.select` (5 values, 3 b) vs `wmon_en`, `wmon_sel[1:0]`; `ctle.config.zero_trim`
(2 b) vs `ctle_peak[2:0]`. The macro exports raw `analog_cfg` bits; only the `EN_EFF_*` state decodes exist
(`rtl/pt_digital_macro.sv:161-186`). Owner: assembly glue or digital.

**D9. `wire_rx_valid` and the wired status bits have no producer.** `rtl/pt_core.sv:87` drops every quad unless `wire_rx_valid`
is high; no analog cell has such an output. Same for cdr_qualified / cdr_loss / rx_state / electrical_quiet. Trivial to tie, but
it must be decided (tie high, or derive from the missing CDR logic of A3). Owner: digital / assembly.

**D10. No signal detect on the HS pair.** `pt_detect` only sees the USB pair or the TX pads (`README.md:804-808`). SATA OOB / PCIe
idle / link-down detection depends on the unimplemented IX-10 + IX-12 route. Owner: wired RX / digital.

### COSMETIC

* `integration/pt_chip.sv:1` still says WIRE_RX is the USB pair; top-level ports predate PD22 (WCLK_OBS, WDBG_OBS kept, USB missing).
* `wire_rx_ptrim_en` (`rtl/pt_digital_macro.sv:49`) is not connected in `pt_chip.sv`.
* `ctle.spice:2` header ("output CM ~1.0 V") contradicts the cell.
* `slicer.spice:7` QCK "for the RTL" has no consumer; the capture uses CKP0.
* `cdr.config.cap_rcsel` is 2 bits for a 1-bit pin (RCS = bit 1; documented in the register map).
* `spec/analog-architecture.json` nets (`SLICER_INPUT` CM 1.65 V, 210 fF; `cdr_phase` 0.4 V differential clocks; `usbhs.conditioned`) describe an older architecture.
* `usbfs.*` fields carry `islands: []` although the pad sits on the wired rail.

## What I could not trace

* Anything at 12 corners: S2, S3 are tt only; S4 is tt/ss/ff op points; S5 is schematic ss only.
* The S1 load numbers are an estimate from the extracted netlists, not an AC measurement, and exclude block-to-block routing.
* Whether the "CTLE-driven" slicer bench (`README.md:985`) included rxselect and wmon_sel, and at what amplitude.
* DX-to-WCLK40 minimum delay of the published `wc_gear` (hold at the macro), and the DX bit order beyond the README statement.
* Isolation / level cells on PH (pll -> wired), UP/DN (wired -> pll), DX (wired -> core): no instances exist to inspect.
* The pad internals: USB HS TX eye, FS/LS driver timing, HS termination at corners (pads owner's evidence only).
* A closed loop with the real capture phase detector: every bench uses a behavioural stand-in (`sims.py:1213-1217`).
* `pt_detect` thresholds against the USB limits at corners; `det_clk` rate needed for 4-UI squelch qualification.
* `hsbias.IBIAS` source (bound to an ATB node name in `BIND`).
* README claim that the published `ptrim.ext.spice` "does not toggle": at 625 MHz tt / 150 fF it toggled in my run; I did not try 834 MHz or ss.
