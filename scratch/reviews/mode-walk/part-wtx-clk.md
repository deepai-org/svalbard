# Mode walk, part: wired TX (CMOS / CML / TMDS / 100BASE-TX / WTX_EXT) and shared clock infrastructure

Reviewer pass 2026-11-13. Read-only on design files. Paths are relative to
`projects/programmable_transceiver_platform` (`$P`) unless they start with `scratch/`.
`IC` = `scratch/reviews/interface-changes.md`. `BIND` = `scratch/integration/m6-powerup/chipnet/binding.json`
(fresh run of `verification/chip_assembly/netlist.py` on the last full floorplan).
Work files of this review: `scratch/reviews/mode-walk/wtx/` (`phswing.py`, `phswing.json`).

Verdicts: OK needs both sides cited. MISMATCH = the two artefacts disagree, or one side does not exist.
UNVERIFIABLE = both sides exist but nothing checks them against each other.

## 0. State of the artefacts (what "the chip" is today)

* `pt_analog_physical` is a blackbox (`integration/pt_chip.sv:119`). The only chip netlist is `netlist.py`.
* In the last full assembly these blocks FAILED placement and are therefore in no chip netlist:
  `pll_tx`, `cdr`, `vreg_tx`, `vreg_cdr`, `attached_tx_buffer`, `wrx_cap`, `pll_host`
  (`scratch/integration/m6-powerup/chipnet/floorplan.json` key `failures`). `BIND` has no `pll_tx` instance.
* The current `verification/chip_assembly/inventory.py` and `netlist.py` contain no `pll_vreg` master at all
  (`grep -i vreg verification/chip_assembly/*.py` is empty) and no `pt_diff_clk_rx` instance on REF_IN
  (instances are `rx_aux_clk`, `rx_wclk_in`, `rx_wtx_ext` only, `inventory.py:309-310`).
* The published `pt_wiredtx` (`analog/wired_tx/wiredtx.spice:1124`, 2026-11-12) is the all-CMOS quarter-rate core
  `wtx_serq4c`. It contains no CML cell. `cml_ser.py` / `sim_cml.py` (wtx_cml2) and `cells_fastpath_wip.py` are
  not instantiated by `cells.py`. An eighth-rate all-CMOS core `wtx_serq8` is being built by another agent
  (`analog/wired_tx/serq8_macro.py`, untracked files in `generated/fast/`); it is not in `pt_wiredtx` either.
* The WT24 CML pre-driver between `pt_wiredtx` and the pad exists only in `scratch/pads-wt24` and
  `scratch/wired_tx/s10/wt24` (IC:1066-1205, review verdict NO-GO at IC:1193).

## 1. Wired TX, retimed CMOS path (<= 2.5 Gb/s)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| digital -> pt_wiredtx | word width, bit order | `rtl/pt_core.sv:242` `wire_tx_data={wire_high,wire_low}`, word 0 in [9:0] (`integration/pt_chip.sv:127`) | `analog/wired_tx/cells.py:869-880` D0 first on the line; `wiredtx.spice:1131-1170` mux D[i]/D[i+20] | OK | 40 bits, D0 first, on both sides |
| digital -> pt_wiredtx | which half loads first | `rtl/pt_core.sv:238-241` wire_low on WORD_CLK40 fall, wire_high on rise | `wiredtx.spice:72-77` (w40: SEL=1 after first WORD_CLK edge), `:79-83` (mux passes A=D[i] when S=1) | OK | D0..D19 while WORD_CLK40 high, D20..D39 while low |
| digital -> pt_wiredtx | launch/capture timing | `integration/pt_digital_macro.sdc:298-310` (lo: launch on fall, needed 0.2 T after rise; hi: needed 0.7 T - 0.5 ns) | `analog/wired_tx/sim_wiredtx.py:171-183` (bench: lo valid 2.0 ns after fall, hi 3.5 ns after rise); IC:223 (WT20: loads at 0.24 T and 0.74 T) | OK | consistent at T >= 16 ns. The clock round trip (WORD_CLK40 -> iso clamp -> macro pin, data route back) is in neither bench: see U3 |
| digital -> pt_wiredtx | stale constraint file | `integration/pt_wired_tx.sdc:4-9` (10-bit word, falling-edge capture of all bits) | `verification/run_p2_synth.sh:141-142` still sources it | MISMATCH | superseded by the macro SDC; cosmetic unless the P2 flow is used for sign-off |
| pt_wiredtx -> digital | `wire_tx_clk` source | `rtl/pt_digital_macro.sv:38` (comment: pt_wiredtx WORD_CLK40) | `verification/chip_assembly/netlist.py:109` binds only `WORD_CLK`; `WORD_CLK40` unbound (BIND `wiredtx.WORD_CLK40`) | MISMATCH | no net carries WORD_CLK40 to `wire_tx_clk` |
| word clock net | drivers of `ct_word_clk` | `rtl/pt_digital_macro.sv:196` (macro OUTPUT `ct_word_clk`) | `netlist.py:109` (`wiredtx.WORD_CLK`, output) and `netlist.py:114` (`wordclk.WORD_CLK`, output) | MISMATCH | three outputs on one net (BIND: `ct_word_clk` = wiredtx.WORD_CLK, wordclk.WORD_CLK, digital.ct_word_clk). Known as IC:602 (PD8), still present |
| digital -> pt_wiredtx | `SER_EN` source | `netlist.py:109` `wiredtx.SER_EN` <- `ct_ser_run`; `rtl/pt_clocktree_slow.sv:169` is the only assignment that sets `ser_run` | `analog/wired_tx/README.md:179` (SER_EN = wiredtx.state active and not debug.wtx_ext) | MISMATCH | see F2: `ser_run` needs an armed, qualified, marker-triggered launch and never clears |
| pt_wiredtx -> digital | `wire_tx_request` | `rtl/pt_core.sv:227` `wire_load=!wire_valid_q\|\|wire_tx_request` | no pin on `pt_wiredtx` (`wiredtx.spice:1124`); no rule in `netlist.py` | MISMATCH | no analog source. Held 0 the stage loads one word and repeats it for ever |
| digital -> pt_wiredtx | `wire_idle` | `rtl/pt_core.sv:244` output | no pin on `pt_wiredtx` (`wiredtx.spice:1124`) | MISMATCH | no electrical-idle path; spec asks for it (`spec/interface-requirements.md:50,75`) |
| regmap -> pt_wiredtx | MODE_H / MODE_F | `spec/register-map.json` `consolidation.wiredtx_stage.bits_per_cycle` (2 b, debug bus 103) and `.rate_mode` (2 b) | `cells.py:862-866` (00 rep1, 10/11 rep2, 01 rep4; only sets the postcursor delay) | MISMATCH | no decoder, pins unbound (BIND). `rate_mode` has no consumer anywhere; `bits_per_cycle` is used only as `cfg_half_rate` (`rtl/pt_digital_macro.sv:193`) |
| regmap -> pt_wiredtx | MAIN_CODE / POST_CODE | `register-map.json` `wiredtx.config.current_code` (analog 502, 8 b, default 109), `.postcursor_code` (510, 8 b, default 0) | `wiredtx.spice:1124` MAIN_CODE0-7, POST_CODE0-7 | UNVERIFIABLE | widths match; all 16 pins unbound in BIND, so the DAC inputs float |
| regmap -> pt_wiredtx | POST_POL | no field (`grep -i post_pol rtl/pt_regmap_defs.svh` is empty; IC:217 asks for `wiredtx.config.post_polarity`) | `wiredtx.spice:1124` POST_POL input | MISMATCH | consumer without a bit |
| regmap -> pt_wiredtx | EN_MAIN / EN_POST | `rtl/pt_digital_macro.sv:163` en_eff[2] (state == 2 and island on); `en_eff` is not connected in `integration/pt_chip.sv:64-88` | `analog/wired_tx/README.md:181` (enables come from the pads interlock); BIND: EN_MAIN = EN_EFF_wiredtx, EN_POST unbound | MISMATCH | three different owners for one pin; `txpad.config.branch` (2 b) has no decoder outside the bring-up cell |
| repetition (x2, x4) | who repeats bits | IC:222 (WT19: the digital repeats) | `rtl/pt_core.sv:205-245` has no repetition; `grep -n "repet" rtl/*.sv` is empty | MISMATCH | 1.25 Gb/s and 480 Mb/s only work if the FPGA pre-repeats every bit |
| ring -> pt_wiredtx | phase pins | `analog/timing/pll_ring_core.spice:38` PH0..PH7 | `wiredtx.spice:1124` WTX_PH0/90/180/270 | UNVERIFIABLE | pins exist; unbound (BIND), `pll_tx` unplaced. No selection of which 4 of 8 is recorded |
| ring -> pt_wiredtx | "via the clockmux" | `analog/wired_tx/cells.py:8-9`, `README.md:175` (phases via the clockmux) | `analog/timing/clockmux.spice:28` (WIRE is one single-ended output) | MISMATCH | the clockmux cannot pass four phases. External wire clocks (WS_REF/WS_AUX/WS_WCK) therefore cannot clock the serializer |
| ring -> pt_wiredtx | swing / domain | `pll_ring_core.spice:6` (ring VDD = pt_pll_vreg output, about 0.9 x rail); `analog/pll_vreg/README.md:39` (VOUT 2.57-3.01 V) | `analog/wired_tx/sim_wiredtx.py:85` (phases swing to the full wired `vdd`) | MISMATCH | no level shifter; bench does not resemble the neighbour. Measured effect: F8 |
| ring -> pt_wiredtx | island crossing | pll island (`inventory.py:289`) | wired island (`inventory.py:304`); `wiredtx.spice:101-104` NAND(PH, MQ) with MQ tied VDD (`:1171`, `cells.py:882`) | UNVERIFIABLE | no iso cell on WTX_PH*. Wired island on with pll island off (the WTX_EXT fallback) leaves these gates undriven |
| ring range | rates | IC:974 (r9d high band at ff/22: 484 MHz at VCTRL 0.87 V; low band needs BAND=0) | `netlist.py:121` BAND tied VDD; no band field in `register-map.json` | MISMATCH | see F5 |
| core_bias -> pt_wiredtx | IBIAS direction, value | `analog/core_support/distribution/generated/pt_bias_bank3.ext.spice:15` (PMOS output, sources) | `wiredtx.spice:1176-1177` (NMOS diode sinks; `cells.py:890` 10 uA) | OK | BIND: `wiredtx.IBIAS` = `BIAS_wiredtx` |
| pt_wiredtx -> pad | MAIN_BIAS / POST_BIAS type | `wiredtx.spice:1118-1119` diode 2 x nfet_03v3 20/1 | `analog/pads/generated/stress-safe-families/wired-transmit/physical.spice:1` pin list; tails 32 x nfet_03v3 20/1 on MAIN_BIAS and POST_BIAS (device count by script) | OK | gate-voltage mirror, same device type and L, ratio 16 |
| pt_wiredtx -> pad | CMD_MAIN/POST drive | `wiredtx.spice:1174` CMD outputs (NAND, about 1 kohm at ss per IC:1089) | pad MAIN_P gate = 8 x nfet_03v3 20/0.28 (`physical.spice`, counted); `netlist.py:105,134` binds CMD straight to the pad gate | MISMATCH | no steering buffer or pre-driver in the netlist (`netlist.py:234` skips `attached_tx_*`). Owner's own bench: published steering buffer drops < 400 ps pulses (IC:227, WT24) |
| pad support pins | CASCODE, TERM_ENABLE, TERM_VCM, DETECT_ENABLE, DETECT_PBIAS | `analog/wired_tx/sim_integration.py:181-186` (ideal 3.3 V / 1.65 V through 2 ohm) | BIND `pad_wire_tx`: all five unbound; `attached_tx_buffer` failed placement | MISMATCH | bench sources are ideal; no real source bound. TX pad has no termination trim (IC:1138) |
| reset / off state | outputs with island off or EN=0 | `wiredtx.spice:1120-1121` (bias pulled low by ENB / ISLAND_OFF), `cells.py:559-569` (CMD clamps) | BIND: `wiredtx.ISLAND_OFF` = `ISLAND_OFF_wired` | OK | block side is safe; but see TMDS pad pins below |
| evidence | netlist the evidence refers to | `analog/wired_tx/generated/wiredtx-evidence.json` `netlist_hashes.extracted` = a8b5f07f... (2026-11-10), `performance_vs_target` = [] | `sha256sum generated/wiredtx.ext.spice` = efcd36f1... (2026-11-12) | MISMATCH | the "record of truth" (`README.md:7`) does not describe the published netlist |

## 2. Wired TX, CML path (2.7-3.24 Gb/s)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| serializer final stage | CML 2:1 present | `scratch/reviews/MANDATE.md` (final 2:1 is CML); `analog/wired_tx/cml_ser.py:1-8` (wtx_cml2) | `analog/wired_tx/wiredtx.spice:974-1010` (`wtx_serq4c`: CMOS window mux `wtx_omuxt`, no cmlt cell) | MISMATCH | the CML stage is not in the published block |
| rate plan | 2.7-3.24 Gb/s | IC:224 (WT21: core never above 2.5 Gb/s), IC:226 (WT23: quantified, NOT built) | `integration/pt_digital_macro.sdc:21-22` (wtx constrained at 12.3 ns = 3.24 Gb/s) | MISMATCH | digital is constrained for a rate no analog block provides |
| serq8 (in flight) | phases | `analog/wired_tx/serq8_macro.py:45-46` (8 phases PH0..PH315, modes M2/R4/R8) | `wiredtx.spice:1124` (4 phase pins, MODE_H/MODE_F) | MISMATCH | top-level pin list must change; assembly and regmap have no rows for it |
| serq8 (in flight) | ring range | `serq8_macro.py:5-6` (n=1: ring 300-405 MHz for 2.4-3.24 Gb/s) | `netlist.py:121` BAND=VDD; IC:974 (high band bottom 484 MHz at ff) | MISMATCH | every x1 rate of serq8 needs BAND=0, which has no register bit |
| serq8 (in flight) | 40-bit load vs split launch | `serq8_macro.py:3-4` (8 streams x 5 bits, whole word loaded at once) | `rtl/pt_core.sv:238-241` (halves launched half a period apart) | UNVERIFIABLE | common valid window is [rise + 3.5 ns, rise + T/2]: 2.7 ns at T = 12.35 ns |
| pre-driver -> pad | CML pre-driver | IC:1156-1193 (cell `wt24_tr7` in scratch; review NO-GO) | pad switch still 8 x 20/0.28 (`physical.spice`), IC:1148 asks for 0.6x resize | MISMATCH | neither the cell nor the resized pad is published; `wtx.predrv_trim[1:0]` and `EN_POST = (post != 0)` have no register or decode |
| CML bench | resembles neighbour | `analog/wired_tx/sim_cml.py:1-8` (ideal streams, tcq swept, schematic) | none | UNVERIFIABLE | never run from the extracted core or into the pad |

## 3. TMDS, 100BASE-TX (IX-9), WTX_EXT fallback

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| pt_wiredtx -> pad | TMDS branch pins | `wiredtx.spice:1124` (no CMD_TMDS_*, TMDS_BIAS, EN_TMDS, TMDS_CODE; removed by WT22, IC:225) | `netlist.py:106-107,135-136` still binds them; pad pins `physical.spice:1` TMDS_P TMDS_N TMDS_BIAS | MISMATCH | BIND: nets `TX_TMDS_P`, `TX_TMDS_N`, `TX_TMDS_BIAS` have the pad as their only pin: floating gates on 8 x 20/0.28 switches and 16 x 20/1 tails on the TX pad, in every mode |
| regmap -> TMDS | code | `register-map.json` `tmds.config.current_code` (analog 440, default 102) | no TMDS_CODE pin (`wiredtx.spice:1124`) | MISMATCH | field without consumer; TMDS now uses MAIN code |
| TMDS rate | ring 371.25 MHz | IC:225 (bench `int_tmds_q1g485` used ring 371 MHz, ideal phases) | IC:974 (BAND=1 bottom 484 MHz at ff); `pll_ring_core.spice:3` (no N5/N10: N = 4, 8, 16 only) | MISMATCH | 1.485 Gb/s needs BAND=0 and a board reference of 371.25/N MHz; a pixel clock (148.5 MHz) cannot be the reference of the TX ring |
| TMDS multi-chip | deterministic launch | `rtl/pt_clocktree_slow.sv:3-5,32,337` (word divider /10 on the bit clock, DDR `bit_phase`) | `wiredtx.spice:432` (own /5 `wtx_div5r`), `:1130` (own /2), no load or phase input | MISMATCH | `ct_word_load`, `ct_bit_phase`, `ct_qualified` have no analog consumer; lane-to-lane alignment of three chips is not defined by any artefact |
| 100BASE-TX | three levels | IC:781 (IX-9: MAIN + POST same sign, zero level = 1010 at core rate, board filter B39) | `wiredtx.spice:1124` POST_POL; `sim_integration.py:318-320` MLT-3 bench | UNVERIFIABLE | mechanism exists in the block; POST_POL has no register bit; no MLT-3 run in `wiredtx-evidence.json` (grep `mlt3`: 0 hits) |
| 100BASE-TX | 125 MBd rate | IC:788 (2 Gb/s core, 16x pattern, ring 500 MHz, coding in the FPGA) | `cells.py:862-866` (rep modes 1/2/4 only) | OK | 16x is done by the FPGA; ring 500 MHz is inside the high band |
| WTX_EXT fixture | builds | `integration/wtx_fallback.py:139-140` adds `TMDS_CODE0..7` to the pt_wiredtx connections; `:144-146` steers CMD_TMDS | `verification/check_chip_power.py:78-79` raises on any pin-set difference; `wiredtx.ext.spice` has no TMDS pin | MISMATCH | the fixture cannot be built against the published block (set difference computed: TMDS_CODE0..7) |
| WTX_EXT control | which branch is enabled | `wtx_fallback.py:108` REQ_MAIN = VSS, REQ_TMDS = TMDS_REQUEST (the published `pt_wtx_fallback_control` cell decodes branch == 2) | `wiredtx.spice:1033,1038` external data reaches CMD only through EN_MAIN | MISMATCH | after X5 the fallback asserts an enable that no longer exists and leaves EN_MAIN low |
| rx_wtx_ext -> pt_wiredtx | DX | `netlist.py:90` `rx_wtx_ext.OUTP` -> net `WTX_EXT_DATA` | `netlist.py:108` `wiredtx.WTX_EXT_DATA` (an OUTPUT, `wiredtx.spice:1034`) on the same net; `wiredtx.DX` unbound (BIND) | MISMATCH | two outputs shorted, the input floats. `analog/wired_tx/wtx_ext_rx.spice:13-21` uses OUTN with swapped legs instead |
| rx_wtx_ext | island | BIND `rx_wtx_ext.VDD` = RAIL_debug | BIND `wiredtx.VDD` = RAIL_wired; `wtx_fallback.py:84-87` crosses through two iso clamps | MISMATCH | netlist crosses debug -> wired with no clamp |
| rx_wtx_ext | data rate | `analog/wired_tx/README.md:13` (extracted receiver: 5/43 errors at 0.5 Gb/s, no output at 2 Gb/s) | fallback purpose (external data at line rate) | MISMATCH | owner's own number |
| WIRED_ON | drivers | `netlist.py` `wtx_fallback_control.WIRED_ON` -> `island_on[0]` (BIND) | `integration/pt_chip.sv:74` `.wired_on_ext(1'b0)` and macro drives `island_on` | MISMATCH | output-on-output (IC:602); the RTL fix (`wired_on_ext` input) is not used by the binding |

## 4. Clock infrastructure, per consumer

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| REF_IN pad -> ref_clk | receiver | `analog/timing/diff_clk_rx.spice:2-3` (one design, instance "REF_IN (refinput)") | `inventory.py:309-310` (no REF instance); BIND `ref_clk` = {pll_cdr.REF, digital.ref_clk} | MISMATCH | `ref_clk` has no driver. Kills every PLL, `pt_vreg_seq` (`rtl/pt_vreg_seq.sv:8-9,13`) and the frequency counters |
| regmap -> refinput | select | `register-map.json` `refinput.select.branch` (analog 400, 2 b) | `diff_clk_rx.spice:65` pins EN, SE | UNVERIFIABLE | no instance, no decode |
| ref_clk -> pll_tx | reference | `netlist.py:113` | `pll_ring_core.spice:38` REF | UNVERIFIABLE | instance unplaced |
| regmap -> pll_tx | EN | `netlist.py:37` uses `wirepll.state.state`, which the regmap drops (`bus` = None) | `rtl/pt_digital_macro.sv:84,178` en_eff[11] = `rfpll.state` and vreg_tx_ok, labelled pll_host (deleted by X1, `inventory.py:275-277`) | MISMATCH | the TX ring has no enable bit that both sides agree on |
| regmap -> pll_tx | N4 / N8 / HOLD / BAND | `register-map.json` `consolidation.pll.feedback_n` (2 b, one field), `.owner`, `.output_divider`, `.phase_tap` | `pll_ring_core.spice:38`; `analog/timing/README.md:92` ("field needed") | MISMATCH | one modulus field for two rings, no decode, no HOLD or BAND bit; BAND tied VDD (`netlist.py:121`) |
| pt_pll_vreg -> rings | supply | `analog/pll_vreg/README.md:3,56` (two instances, BYP reset 1); `rtl/pt_digital_macro.sv:174-177` (bypass bits, sequencer) | `inventory.py` (no vreg master); BIND `pll_cdr.VDD` = RAIL_pll | MISMATCH | regulator, its BYP pins and `pllvreg.config.*` have no place in the netlist. Ring range 393-834 MHz is quoted on the regulated supply only (`pll_ring_core.spice:6-7`) |
| core_bias -> pll_tx | IBIAS | `pt_bias_bank3.ext.spice:15` (PMOS source) | `pll_ring_core.spice:42` (NMOS diode sink) | OK | direction agrees; BIND shows `EN_pll_ring_tx` / `BIAS_pll_ring_tx` unbound because pll_tx is unplaced |
| pll_tx -> digital | LOCK, FBCK | `netlist.py:115-116` (`fc_src[0]`, `analog_status[0]`) | `rtl/pt_digital_macro.sv:196` `ct_pll_lock` | UNVERIFIABLE | `analog/timing/README.md:197` says LOCK is wrong at 810 MHz and host_follow; it gates `qualified` (`pt_clocktree_slow.sv:129-130`) |
| clockmux selects | one-hot decode | `analog/timing/README.md:83-92` (glue table; two rows say "field needed") | `clockmux.spice:23-26`; BIND: all 30 signal pins unbound | MISMATCH | no decoder exists in RTL or analog. `clockmux.config.rf_source` / `.wire_source` (analog 119, 121) have no consumer; PS_* has no field |
| clockmux -> prescale | CK_IN | `analog/timing/prescale.spice:4` (240 MHz - 2.5 GHz from "clockmux WIRE_P") | `clockmux.spice:3-4` (single-ended, <= 1 GHz) | MISMATCH | stale header; with the ring <= 834 MHz the range is fine |
| prescale -> digital | `ct_wclk` frequency | `prescale.spice:6-8` (pick ratio so CK_OUT <= 150 MHz) | `integration/pt_digital_macro.sdc:31` CTW_PERIOD 6.4 ns | OK | ring 625 MHz needs D4 |
| prescale | number of instances | `clockmux.spice:9-14` (CONV_INT, HOST_INT, HF are each "prescale" outputs); `rtl/pt_digital_macro.sv:66` (ct_wclk, ct_det_clk_in) | `inventory.py:292` one `prescale` | MISMATCH | five differently divided clocks, one divider with one output |
| regmap -> prescale / wordclk | D2..D16, D10/D20, EN | `register-map.json` `clocktree.config.wire_output_divider` (2 b), `.sample_divider` (2 b), `.wire_host_divider` (6 b, default 16) | `prescale.spice:12`, `wordclk.spice:31` | MISMATCH | binary fields, one-hot pins, no decoder; these fields have no RTL consumer either |
| pt_wordclk | consumer on the TX side | `analog/timing/wordclk.spice:2` (shared TX/RX word divider), `analog/timing/README.md:80` (replaces the TX /5) | `wiredtx.spice:432,1171` (own /5), no LD/LDE pin on `pt_wiredtx` | MISMATCH | for TX the cell is an orphan whose output is shorted onto `ct_word_clk` |
| pt_clocktree_slow | clock model | `rtl/pt_clocktree_slow.sv:337` (wclk = bit clock or half-rate clock), `:344` (reference = line rate / 10) | `prescale.spice:12` (ring / 2..16), `pll_ring_core.spice:3` (reference = ring / 4, 8, 16) | MISMATCH | qualification needs reference period = exactly 10 or 5 wclk cycles (`pt_clocktree_slow.sv:153`); all available ratios are powers of two |
| ct_ref_clk, ct_det_clk_in | source | `integration/pt_chip.sv:143` (analog outputs) | BIND: only `digital.ct_ref_clk`, `digital.ct_det_clk_in` on those nets | MISMATCH | no analog driver |
| detector clock | rate | `spec/clock-rate-ownership.md:20` (250-500 MHz); `pt_clocktree_slow.sv:255-264` (divide the wire clock, up to 2.5 GHz) | `integration/pt_digital_macro.sdc:26` (ctdet 156.25 MHz) | MISMATCH | std cells cannot take or make a 250-500 MHz clock under this constraint |
| clockmux -> ADC/DAC | CONV_CLK | `clockmux.spice:30` (one single-ended CONV_CLK) | `analog/converters/adc_i.spice:413`, `dac_i.spice:1196` (CLKP and CLKN) | MISMATCH | no complement generator; all four pins unbound in BIND |
| clockmux -> digital | HOST_CLK -> `host_word_clk` | `clockmux.spice:31` | `rtl/pt_digital_macro.sv:30` (line/16 or fixed 156.25 MHz); `pt_digital_macro.sdc:31` (6.4 ns) | UNVERIFIABLE | unbound; line/16 = ring/4 only at 625 MHz |
| pt_aosc | enable | `register-map.json` `core.aosc.enable` (debug 246, default 1) | BIND `aosc.EN` unbound; `inventory.py:535` ("aosc EN not yet controllable") | MISMATCH | bit exists, not wired |
| macro -> analog | `en_eff`, `island_off` | `rtl/pt_digital_macro.sv:94` (outputs) | `integration/pt_chip.sv:64-88` (not connected), `:119-140` (no such port) | MISMATCH | `netlist.py` re-derives the decodes as unnamed glue (BIND `glue`), for which no cell exists |
| spec nets | TX clock contract | `spec/analog-architecture.json` `nets.TX_CLOCK` (differential, 0.4 V peak, 0.48-2.5 GHz) and `nets.serial` (1 conductor) | `wiredtx.spice:1124` (four CMOS phases, 40-bit word) | MISMATCH | spec contract is stale |

## 5. Findings, ranked

### DEAD MODE

**F1. No reference, no TX ring, no ring regulator in the chip netlist.** `ref_clk` has two loads and no driver:
there is no `pt_diff_clk_rx` instance on REF_IN (`inventory.py:309-310`; BIND net `ref_clk`). `pll_tx` (with `cdr`,
`vreg_tx`, `vreg_cdr`, `attached_tx_buffer`) failed placement (`floorplan.json` `failures`) and the current inventory
has no `pll_vreg` master. Reproduce: `python3 -c "import json;b=json.load(open('scratch/integration/m6-powerup/chipnet/binding.json'))['bindings'];print('pll_tx' in b,[i+'.'+p for i in b for p,v in b[i].items() if v['net']=='ref_clk'])"`
-> `False ['pll_cdr.REF', 'digital.ref_clk']`. Every wired TX mode, and everything that counts on `ref_clk`
(`pt_vreg_seq`, frequency counters), has no clock. Owner: assembly / integration, with timing.

**F2. `SER_EN` can never be asserted.** `netlist.py:109` drives `pt_wiredtx.SER_EN` from `ct_ser_run`.
In `rtl/pt_clocktree_slow.sv` `ser_run` is set in exactly one place (`:169`, `if (rephase)`), which needs a launch
request from `pt_ct_launch`: `sync_arm`, 64 qualified reference periods, an SPI marker and a reference count. The
qualification needs `ct_ref_clk` (no analog driver, BIND) with a period of exactly 10 or 5 `ct_wclk` cycles
(`:153`), while every divider on the analog side is a power of two. `ser_run` also never clears except by chip
reset, so MODE cannot be changed "while stopped". The block README's intended source
(`README.md:179`, state == active and not wtx_ext) is implemented nowhere. With `SER_EN` low `WORD_CLK40`
does not toggle and the whole `wire_tx_clk` domain is unclocked. Owner: digital + wired TX (decide the source),
assembly (binding).

**F3. `wire_tx_request` has no source.** `rtl/pt_core.sv:227` only advances the output stage when the analog side
asserts it; `pt_wiredtx` has no such pin and `netlist.py` has no rule. Tied low, one word is loaded and repeated
for ever; left floating it is undefined. Owner: integration (tie to the serializer-running level) + digital.

**F4. WTX_EXT fallback is broken on four counts.** (a) `integration/wtx_fallback.py:139-146` connects TMDS pins
that `pt_wiredtx` no longer has, and `check_chip_power.py:78-79` raises on that, so the fixture cannot be built
(mechanical check in this review: extra keys `TMDS_CODE0..7`). (b) The published control cell requests the TMDS
branch (`wtx_fallback.py:108`), but after X5 external data needs `EN_MAIN`. (c) `netlist.py:90,108` puts
`rx_wtx_ext.OUTP` and the `pt_wiredtx.WTX_EXT_DATA` output on one net and leaves `DX` unbound. (d) the extracted
receiver fails from 0.5 Gb/s (`analog/wired_tx/README.md:13`). Owner: wired TX (fixture, control decode),
assembly (binding), timing (receiver).

**F5. Ring band bit and TX-ring modulus: several protocol rates have no legal setting.** `BAND` is tied high
(`netlist.py:121`) and has no register field. The owner's extracted high-band bottom at ff/22 is 484 MHz
(IC:974), so ring 371.25 (TMDS 1.485), 375 (SATA 1.5), 405 (DP RBR 1.62) and, marginally, 480 MHz (USB HS x4) are
not guaranteed. `pt_pll_ring_core` has N = 4/8/16 only (`pll_ring_core.spice:3`) and the reference divider was
dropped from the regmap (`refinput.select.reference_divider`, bus None), so each rate also needs its own board
reference of ring/N. Owner: digital (bits `ring_l.band`, per-ring modulus and enable), timing, board spec.

**F6. 2.7-3.24 Gb/s (CML path) does not exist as hardware.** No CML cell in `pt_wiredtx`
(`wiredtx.spice:974-1010`), rate plan capped at 2.5 Gb/s (IC:224), CML pre-driver unpublished and reviewed NO-GO
(IC:1193). The MANDATE's "final 2:1 is CML" is not met by the published block or by the in-flight `wtx_serq8`
(all CMOS). Owner: wired TX.

**F7. 100BASE-TX: `POST_POL` has no register bit.** The MLT-3 mechanism (MAIN + POST same sign) is in the block,
but `wiredtx.config.post_polarity` (IC:217, IC:781) was never added (`rtl/pt_regmap_defs.svh`). Owner: digital.

**F8. TX pad TMDS branch floats.** `netlist.py:106-107,135-136` binds pad `TMDS_P/N/TMDS_BIAS` to nets whose
driver pins were removed from `pt_wiredtx` (WT22). The tail gate of a 16 x 20/1 um sink and both switch gates on the
WIRE_TX pad are undriven in every mode. Classified dead because an undefined static current on the output pad
corrupts every TX mode. Owner: pads (tie-off or remove the branch), assembly.

### DEGRADED

**F9. Ring phases do not swing to the serializer's rail.** The ring runs on 0.9 x rail (2.57-3.01 V), the
serializer on the wired rail; `sim_wiredtx.py:85` drives full-rail phases. Schematic check of the phase input stage
(`scratch/reviews/mode-walk/wtx/phswing.py`, ring 625 MHz, 150 ohm source): duty at the window driver `QW` falls
from 0.487 to 0.478 (tt, 0.9 x VDD) and to 0.453-0.465 at 2.57 V across tt/ss/ff/fs/sf, i.e. 15-50 ps less window
at a 400 ps UI, where the owner's pessimistic eye is 171 ps. Static current change is below 50 uA. The source edge
shape is my assumption, so treat the numbers as an estimate. With bypass (reset default) the swing is full but the
supply-induced jitter is 33 ps peak (`analog/pll_vreg/README.md:41`). Owner: wired TX + timing (bench with the real
phase buffer, or a level-restoring stage).

**F10. `ct_word_clk` has three drivers, `island_on[0]` two** (BIND; IC:602 known, not fixed in `netlist.py:109,114`).
Owner: assembly.

**F11. No control decode anywhere.** Clockmux (16 one-hot selects), prescale, wordclk, MODE_H/F, PLL N/HOLD, EN_POST
have binary register fields or none and no decoder cell (`analog/timing/README.md:83-92` is a table, not a cell).
The macro's own `en_eff` / `island_off` outputs are not connected (`pt_chip.sv:64-88`). Owner: digital + integration.

**F12. Clock-tree RTL models a different serializer.** `pt_clocktree_slow` divides a bit clock by 10 and hands out
`word_load` / `bit_phase`; the analog serializer has its own /5 and /2 and takes neither. Multi-chip TMDS
alignment therefore has no defined mechanism. One `pt_prescale` serves five clock needs. Owner: digital + timing.

**F13. No bit repetition in RTL** (WT19 approved, not built): x2 / x4 rates depend on the FPGA. `rate_mode` is a
dead field. Owner: digital.

**F14. No electrical idle.** `wire_idle` and `wiredtx.idle.idle` (default 1) have no consumer in `pt_wiredtx`;
SATA OOB and PCIe idle are required by `spec/interface-requirements.md:50,75`. Owner: wired TX + spec.

**F15. 2.0-2.5 Gb/s fails at the pad with published cells** (owner's WT24 bench, IC:227), and the netlist has no
buffer between CMD and the pad gates at all. TERM_VCM / CASCODE sources are ideal in every bench. Owner: wired TX
(now owns WT24), pads.

**F16. Evidence does not match the artefacts.** `wiredtx-evidence.json` hashes are of the 11-10 netlist and its
result list is empty; `evidence/digital-hardening-evidence.json` (11-10, run CLOSE_R2) records ss setup slack
-7.43 ns (`wtx`) and -12.32 ns (`egress_wtx`) at 12.3 ns, which would also fail 16 ns; the later closure is not in
the evidence file. Owner: wired TX, digital.

### COSMETIC

* `integration/pt_wired_tx.sdc` and `integration/macro-contract.md:138,149` describe the 10/20-bit boundary.
* `analog/timing/prescale.spice:4` and `analog/wired_tx/README.md:175-183` describe removed clocks and pins
  (EN_TMDS, TMDS_CODE, generic serializer, "via the clockmux").
* `spec/analog-architecture.json` nets `TX_CLOCK`, `serial`, `wire_pll` describe a full-rate differential clock.
* `tmds.config.current_code`, `clockmux.config.*`, most of `clocktree.config.*`, `consolidation.pll.owner/phase_tap/output_divider` have no consumer.
* `rtl/pt_digital_macro.sv:84` still names en_eff[11] `pll_host`.

## 6. Not traced

* U1. Ring phase quality at the serializer pins (spacing, duty, jitter of the extracted `ct_phbuf8` into the
  routed load). No bench joins `pt_pll_ring_core` to `pt_wiredtx`; block benches use ideal phases.
* U2. Ring stop state against the serializer's expected stop levels (PH0 = PH90 = 0, PH180 = PH270 = 1).
* U3. WORD_CLK40 round trip: wired island -> iso clamp -> macro clock tree -> launch flops -> route -> D pins.
  Neither the SDC nor the block bench contains the clamp or route delays.
* U4. Pad output swing, common mode and return loss against PCIe / SATA / TMDS levels, package channel
  (`spec/package-channel.json`), T-coil reserve, interlock sequencing (`rtl/pt_tx_pad_sequence.sv` is instantiated
  nowhere in `rtl/` or `integration/`).
* U5. Host-clock and converter-clock frequency plans per mode (clockmux fully unbound; no decode to walk).
* U6. `pt_aosc`, `pt_clk_obs` behaviour beyond pin binding; LOCK detector validity.
* U7. Current state of `scratch/wired_tx/s10/wt24` (r7 pre-driver) and of `wtx_serq8` simulations: in progress by
  another agent, not reviewed.
* U8. Digital timing of the `wire_tx_clk` domain on the current RTL (only the 11-10 evidence was read).
