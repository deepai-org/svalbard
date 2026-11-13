# Mode walk, part DIG: host link, SPI-only bring-up, ATB / debug observation

Date 2026-11-13. Read-only review of the working tree (dirty; `rtl/gen/gen_regfile.py`, `rtl/pt_regfile.sv`,
`rtl/pt_digital_macro.sv`, `integration/pt_chip.sv` were modified at 20:49-20:51 today by another agent).
`$P` = `projects/programmable_transceiver_platform`. `BIND` = `scratch/integration/m6-powerup/chipnet/binding.json`
(today's run of `$P/verification/chip_assembly/netlist.py`). `IC` = `scratch/reviews/interface-changes.md`.
`R4LEF` = `scratch/digital-hardening-ac1-r4/design/runs/AC1_R4/final/lef/pt_digital_macro.lef` (2026-11-11 01:46,
the newest hardened macro abstract on disk; `chipnet/digital.json` has the same pin set).

Checks run (work dir `scratch/reviews/mode-walk/dig/`):

- `iverilog -g2012 -Dfunctional -DPT_EXTERNAL_IO -I $P/rtl -s tb_chip_io $P/sim/tb_chip_io.sv $P/integration/pt_chip.sv
  $P/integration/pt_provider_io.sv $P/rtl/*.sv <frozen-pdk>/gf180mcu_fd_io.v` elaborates without port errors;
  `vvp` FAILS at `tb_chip_io.sv:50` (`read 08: got 0003 expected 0002`): the bench still reads RESET_STATUS at
  0x08, it is at 0x0D now (`pt_regfile.sv:2797`). With that one line changed (`dig/tb_chip_io_local.sv`,
  `read_reg(8'h0d,16'h0003)`) the bench prints `CHIP_IO_PASS`.
- Python cross-checks of `register-map.json` fields against `BIND` consumers, LEF pin counts, ATB node sources
  (inline scripts, results quoted below).

Not simulated: anything transistor-level. The power-up / isolation audit in `scratch/integration/m6-powerup`
(K1-K7 rules) is referenced, not repeated.

---

## 1. Host D2H (chip -> FPGA)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| pt_chip -> pt_host_physical | positional port order | `integration/pt_chip.sv:46-48` | `integration/pt_chip.sv:102-108`, `integration/pt_provider_io.sv:6-13` | OK | same 27 ports in the same order; elaborates |
| macro -> D2H pad cells | pin names, OE polarity, drive/slew pins | `pt_provider_io.sv:54-59` (bi_t: A, OE, PDRV0=drive[0], PDRV1=drive[1], SL, IE=0) | `gf180mcu_fd_io.v:131-152` (`bufif1 (PAD,A,OE)`) | OK | OE active high; `d2h_oe = d2h_enable` (`rtl/pt_host_link.sv:137`), reset 0 -> tristate |
| D2H[0] pad site | cell type at `clk_pad` (in_s in the provider template) | `pt_chip.sv:95-97` | `verification/chip_assembly/inventory.py:229`, `kl_assemble.py:70-75` (`d2h0_at_clk_pad`) | OK | substitution is checked by the assembly script |
| reset defaults -> pad speed | drive/slew default vs 156.25 MHz DDR | `rtl/pt_regfile.sv:1642-1643` (drive=1 -> PDRV0=1,PDRV1=0; slew=1) | `evidence/digital-hardening-evidence.json` hostio.pad_toggle_screen: bi_t `PDRV0&!PDRV1&SL` f_ddr_max 140.8 MHz @5 pF, 108.5 MHz @10 pF (tt) | MISMATCH | default pad setting is below full rate; host must write drive=3 (215/183 MHz tt @5/10 pF), slew=0 before `d2h_enable`. Not stated in `spec/fpga-connection-plan.md` |
| macro D2H pins -> south pads | where the DDR launch happens | `rtl/pt_host_link.sv:107-121,197` and `rtl/pt_digital_macro.sv:155-160` (gearbox + launch flops inside the macro, pins `d2h_pin[9:0]`, `d2h_clk_pin`) | `verification/chip_assembly/inventory.py:482-486` (`rsv_d2h_gearbox` at the south pads; corridor carries "D2H word/4"); `IC:312` ("I3: option (b) accepted. The word/4 side crosses the corridor") | MISMATCH | the floorplan assumes a pad-edge gearbox cell fed by a 40-bit word/4 bus; no such cell exists (reserve is an empty rectangle, no master in inventory). Implemented macro sends 11 DDR lanes (3.2 ns UI) from its S edge (y 3215) to pads at y < 442: >= 2.7 mm plus up to ~1.9 mm lateral |
| macro D2H pins -> pads | skew budget | `IC:908` (T25: +-0.64 ns spent at the macro pins, "route length-matched") | no top-level route, no extraction | UNVERIFIABLE | nothing constrains or checks the 2.7-4.6 mm routes |
| host clock source | what drives `host_word_clk` | `pt_chip.sv:52,65` (`ht` = `pt_analog_physical.host_tx_clk`) | `analog/timing/clockmux.spice:12-13,31` (HOST_CLK = HS_INT ring/prescale or HS_HF host_follow only) | OK (as designed) | consequence: no ring PLL -> no D2H and no H2D. REF_IN or H2D_CLK cannot clock the link directly |
| host clock source, assembled | binding | `BIND` clockmux: all 30 signal pins `UNBOUND_clockmux_*`; `digital.host_word_clk` net has no other pin | `verification/chip_assembly/netlist.py` (no rule for clockmux) | MISMATCH | no artefact connects HOST_CLK to the macro; `pll_tx` (source of HOST_INT) is in `floorplan.json` `failures` |
| host clock select decode | field encoding vs cell pins | `spec/debug-controls.json` `debug.clk_select.host_clk` (3-bit enum: 1 internal_pll, 5 host_follow) -> `debug_cfg` raw | `clockmux.spice:23-25` one-hot `HS_INT`, `HS_HF` | MISMATCH | no decoder exists in the macro (exports raw fields + 20 `en_eff`, `pt_digital_macro.sv:94`) or as an analog cell |
| host_follow | H2D_CLK into the clock mux | `clockmux.spice:23,27` (`H2D` input, `PS_H2D`) | `pt_chip.sv:119-148` (`pt_analog_physical` has no h2d_clk port; `h2d_clk` goes only to the macro, `pt_chip.sv:48,65`) | MISMATCH | host_follow (the host/converter clock in passive-LO RF mode) has no path at chip level |
| host clock when pll island off | isolation of the macro clock input | `BIND` clockmux VDD = `RAIL_pll` | `scratch/iso-family/publish/iso-placement.json` (no entry for HOST_CLK / host_word_clk / ref_clk) | MISMATCH | in the SPI-only state the macro's `host_word_clk` (and `ref_clk`) input would float; `pt_host_rate_clock` is not held in reset by anything but `rst_n` (`pt_digital_macro.sv:135`) |
| D2H observability without FPGA capture | liveness | `rtl/pt_digital.sv:50,43` (`host_rx_div` = obs_status[30]) | `spec/register-map.md:264` (DBG_OBS code 4+n -> 34) | OK | host clock /4 visible on DBG_OBS0/1 |
| hardened macro vs RTL | host-link pins | `rtl/pt_digital_macro.sv:30-33` | `R4LEF` (d2h_pin 10, d2h_clk_pin, d2h_oe, d2h_pdrv 2, d2h_sl, host_word_clk present) | OK | host pins unchanged; see F2 for the stale buses |
| FPGA plan vs RTL | DDR, edge-aligned clock, 156.25 MHz | `spec/fpga-connection-plan.md:35,65` | `rtl/pt_host_link.sv:34-38`, `rtl/pt_digital_macro.sv:17-19` | OK | |
| FPGA plan vs RTL | RX2 / `hostio.lane_dir` reversible north bank | `spec/fpga-connection-plan.md:22-23,62,65,157` | `spec/register-map.json` (no `lane_dir` field); `pt_provider_io.sv:48-52` (H2D pads OE=0 hard) | MISMATCH | plan budgets 20 D2H lanes in RX2; not in RTL, regmap or pad binding |

## 2. Host H2D (FPGA -> chip)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| H2D pads -> macro | cell, IE, thresholds, pulls | `pt_provider_io.sv:22-24,48-52` (bi_24t OE=0 IE=1 CS=0 PU=PD=0) | `gf180mcu_fd_io.v:64` (`and (Y,PAD,IE)`), `pt_chip.sv:94` | OK | inputs float while the FPGA is unconfigured (also in `m6-powerup/audit/iso_audit.json` pads) |
| H2D capture clock | which clock captures | `rtl/pt_host_link.sv:140` (h2d_clk -> pt_h2d_gearbox) | `pt_chip.sv:60-61` | OK | |
| H2D needs host_word_clk | reset release | `rtl/pt_digital_macro.sv:138,155` (`host_rst_n = rst_n & rate_hold_n`), `rtl/pt_host_link.sv:480` (hold_n reset 0, released by `clk`) | `clockmux.spice:31` | OK (as designed) | H2D cannot be exercised with H2D_CLK alone; same single point as D2H |
| H2D pad speed | bi_24t input f_max | `evidence/digital-hardening-evidence.json` hostio: `!CS&IE&!OE` 235 MHz tt, 191.6 MHz ss_125C_2v97 | target 156.25 MHz | OK | CS=0 is required (CS=1: 148 MHz at ss) and is what the binding ties |
| H2D pads -> macro distance | placement | `inventory.py:396` (macro top at y 4670), `pin_order.cfg:12` (h2d on N) | `spec/contract.json` candidate_signal_sites H2D bidir[26..36] | OK | pads abut the macro north edge; `rsv_h2d_gearbox` is likewise an empty reserve but nothing is needed there (`IC:580`) |
| macro timing | h2d / hcore closure | `scratch/digital-timing-close/NOTES.md` (TC2A: h2d -3.57, hcore -5.63, hddr -1.91 ns at ss_032C) | `integration/pt_digital_macro.sdc:71,78,126,137` | UNVERIFIABLE | not closed; committed evidence file is two architectures old (F2) |
| fallback when the link is down | capture/playback over SPI | `rtl/pt_digital.sv:119-129` (MEMORY v3, core reset from `rst_n`, SCLK port) | - | UNVERIFIABLE | exists in RTL; still needs wire/rf clocks from analog, so not an SPI-only function |

## 3. SPI-only bring-up

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| RESET_N pad | cell, pull | `pt_provider_io.sv:14-15` (in_c PU=0 PD=1) | `pt_chip.sv:91`, `inventory.py:230` | OK | provider Verilog ignores PU/PD; bench checks the tie only |
| RESET_N board side | open-drain supervisor vs pad pull-down | `spec/board-requirements.md:11` (B1 open-drain) | `pt_provider_io.sv:14` (PD=1) | UNVERIFIABLE | an open-drain driver against an on-chip pull-down needs a board pull-up much stronger than the pad PD; no value is specified |
| reset function | macro vs chip glue | `rtl/pt_digital_macro.sv:96` | `pt_chip.sv:45` | OK | same expression; the analog-side `rst_n` AND/OR in `pt_chip.sv:45` has no cell |
| POR -> macro | pin, polarity | `analog/core_support/por/netlist/schematic/gf180mcu_ocd_ip__por.spice:2` (`porb`) | `netlist.py:124` (`por.porb` -> `por_n`), `rtl/pt_digital_macro.sv:26,96` | OK | release ~40 ms tt per `m6-powerup/sim/results.json` |
| por_bypass strap | pad | `pt_chip.sv:40-44` (`wire por_bypass=1'b0`, "no pad is bound yet") | `rtl/pt_digital_macro.sv:11-16` (expects a strap pad with pull-down) | MISMATCH | a POR that never releases = die permanently in reset; no pad site assigned |
| por_bypass readback | generator vs generated RTL (in flight) | `rtl/gen/gen_regfile.py:512,849,870` (pt_regfile/pt_mgmt gain a `por_bypass` port) | `rtl/pt_regfile.sv:5117` (no such port), `rtl/pt_digital.sv:51` (does not pass it) | MISMATCH | after the next regeneration `pt_digital.sv` leaves the new input unconnected |
| SPI pads | cells, ties, MISO OE | `pt_provider_io.sv:16-21` | `pt_chip.sv:92-93`, `rtl/pt_spi.sv:33-34` (`miso_oe = rst_n && !cs_n`) | OK | bench: MISO hi-Z in reset and with CS_N high |
| SPI ABI | mode 0, 32-clock frame, ID | `rtl/pt_spi.sv:1-2,31` | `spec/debug-controls.json` spi_abi; bench read 0x00 = 0x5356 | OK | |
| SPI pads -> macro in the chip netlist | connectivity | `BIND` dangling: `spi_sclk`, `spi_cs_n`, `spi_mosi`, `spi_miso`, `spi_miso_oe`, `reset_n_pad` | `pt_chip.sv:46-48,64-65` | MISMATCH | the only chip-level SPICE netlist has no host/SPI/RESET pad cells; the path exists only in Verilog with functional pad models. No LVS-grade artefact can catch an open SPI route |
| chip IO bench | regression state | `sim/tb_chip_io.sv:68` (`read_reg(8,16'h0002)`) | `rtl/pt_regfile.sv:2797` (RESET_STATUS at 0x0D) | MISMATCH | bench fails today; last pass `scratch/chip-io/report.json` 2026-11-09 |
| SCLK timing | macro | `scratch/digital-timing-close/NOTES.md` (TC2A sclk +14.1 ns at 10 MHz, ss_032C) | `spec` target 20 MHz in the committed evidence | OK at 10 MHz | 2.9 mm pad->macro route not modelled (`y_load_pf` 0.1 in the pad screen) |
| island switches | EN/PG polarity and bit index | `rtl/pt_regfile.sv:415-426` | `netlist.py:249-252`, `inventory.py:237`, `analog/island_support/README.md:53-55` | OK | conv = 4, debug = 5 on `island_en`; note the debug-bus copies sit at debug_cfg[3],[4] |
| usb island bit | reserved bit handling | `rtl/pt_regfile.sv:90,421-422` (constant 0) | `spec/debug-controls.json` islands.usb ("island_pgood[3] must be tied 0"); `BIND` `island_pgood[3]` dangling | MISMATCH (minor) | floating macro input; no tie-off in any artefact |
| island_on[0] | drivers | `rtl/pt_digital_macro.sv:54-57,188` (`wired_on_ext` input, ORed) | `netlist.py:128` (`wtx_fallback_control.WIRED_ON` -> `island_on[0]`), `pt_chip.sv:74` (`.wired_on_ext(1'b0)`) | MISMATCH | PD8 fixed only on the RTL side: the netlist still shorts two outputs (also K5 in `iso_audit.json`); they disagree whenever `pgood_override.wired` is used |
| bandgap trim | 5-bit field vs 16 pins | `rtl/pt_regfile.sv:992-993` (count -> thermometer, debug_cfg[188:173]) | `integration/core_bias.py:61-63,111`; `analog/core_support/lvs_reference/gf180mcu_ocd_ip__bandgap.sch.spice:2`; `analog/core_support/README.md:277` | OK | default count 8 |
| biasgen / refchain fields | widths, defaults, pins | `spec/register-map.json` core.biasgen.* / core.refchain.* (debug_cfg[142..193]; ena, bgap_ena, dist_en_* default 0; idac2_source 10) | `core_bias.py:55-68,94-111,116`; `BIND` core_bias `C_*` all bound | OK | everything off at reset; `ref_sel_fine` gated by coarse in hardware |
| bias_ready status | source | `rtl/pt_digital.sv:41` (analog_status[2]) | `core_bias.py:84,137` pin list (no ready output) | MISMATCH | status bit has no source |
| fault input | source | `rtl/pt_regfile.sv:444-729` (forces 18 TX-side outputs), `rtl/pt_digital_macro.sv:47` | no `fault`/monitor pin in any subckt (`scratch/reviews/mode-walk/pins.json`); `BIND` `fault` dangling | MISMATCH | "monitor" block (monitor.config.* 75 bits, ATB code 4) does not exist; a floating-high `fault` disables every TX path |
| aosc enable | field -> pin | `rtl/pt_regfile.sv:533,1009,1577` (debug_cfg[246], reset 1) | `analog/timing/aosc.spice:19`; `BIND` `UNBOUND_aosc_EN` | MISMATCH | plain wire missing (K6 in `iso_audit.json`) |
| aosc_div status | source | `rtl/pt_digital.sv:42` (analog_status[11]) | `aosc.spice:19` (only `CLK`), `netlist.py:116` (CLK -> fc_src[4]) | MISMATCH | no divider cell |
| ref_clk | driver | `rtl/pt_digital_macro.sv:35,174` (vreg sequencer, freq counters) | `BIND`: net `ref_clk` has `digital.ref_clk` and `pll_cdr.REF` only (two inputs); no REF_IN receiver instance | MISMATCH | no `pt_diff_clk_rx` for REF_IN in the instance list; `ref_present` (analog_status[1]) has no source either |
| hardened macro vs RTL | control bus widths | `rtl/pt_regmap_defs.svh:2-4` (579 / 256 / 58) | `R4LEF`: analog_cfg 568, debug_cfg 255, atb0_sw/atb1_sw 57; no `wire_rx_ptrim_en`, no `rf_tx_clk_out` | MISMATCH | F2 |
| macro contract doc | widths | `integration/macro-contract.md:53-54` (509 / 107) | `rtl/pt_regmap_defs.svh:2-3` | MISMATCH (doc) | |
| chip-level glue | cells for chip-level expressions | `pt_chip.sv:81` (`sclk&cs_n`), `:82` (`ct_cfg_det_en` from analog_cfg) | no glue cell in inventory | MISMATCH (minor) | |
| legacy ports | consumers | `rtl/pt_digital_macro.sv:44-45` (enable, mode8, rf_trim, wire_trim, clock_trim, calibration_trial) | `BIND`: 0 consumers for all 63 pins; `rtl/pt_digital.sv:167-170` (calibrator removed) | MISMATCH (cosmetic) | dead macro pins; `calibration_above_target` input undriven |

## 4. ATB / debug observation

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| ATB code -> one-hot | decode, width | `rtl/pt_regfile.sv:1015-1072` (sw[k] = code k+1) | `integration/atb_tree.py:38-39` (`ATB{bus}_SW_{code-1}`) | OK | |
| ATB groups / pad enable | group ORs | `rtl/pt_regfile.sv:1133-1140` | `spec/debug-controls.json` atb_groups; `atb_tree.py:45-55` | OK | |
| ATB width | 58 codes | `rtl/pt_regmap_defs.svh:4`, `rtl/pt_regfile.sv:1072` (code 58 vco_replica_vctrl) | `R4LEF` (57 bits); `BIND` (no leaf 58; `vco_replica.VCTRL` unbound) | MISMATCH | newest code has no pin on the hardened macro and no leaf in the assembly |
| ATB bring-up nodes | node -> cell pin | codes 1, 3, 5-14, 22, 29, 35, 55-57 | `BIND` leaves -> `core_bias.ROOT_REF/VCM/TRK_*/VBG/IDAC1`, rails, VSS (`core_bias.py:82-84`) | OK | the reference chain and all five island rails are observable |
| ATB code 2 master_vref0 | node | `BIND` `atb1_leaf2.NODE` = `VREF0_CONV` (only other pin: `refbuf.VREF0`, an input) | `BIND` `core_bias.VREF0` -> `ATBN_master_vref0` (dangling) | MISMATCH | the leaf and refbuf sit on a net with no driver; core_bias VREF0 goes nowhere |
| ATB unbound sense nodes | node -> cell pin | codes 4, 15, 23, 25, 27, 30, 31, 32, 34, 36, 41 | `BIND` `UNBOUND_atbnode_*` / `VCM_RF` (no source) | MISMATCH | incl. pll_vctrl, cdr_bias, conv_vref (the one `override` node), monitor_por_threshold |
| ATB codes 43-54 | characterization structures | `spec/debug-controls.json` atb_nodes 43-54; `analog/characterization/pt_char_atb.spice:2` | `inventory.py` (no char master), `floorplan.json` placed list (no char instance) | MISMATCH | 12 force/sense codes (24 leaves) lead nowhere; cells exist only as blocks |
| ATB vs pgood_override | island gating | `rtl/pt_regfile.sv:1029-1056` (`&&island_on[k]&&island_pgood[k]`) | `rtl/pt_regfile.sv:416-426` (island_on honours override) | MISMATCH | with a failed PG detector and override set, island ATB nodes stay closed |
| ATB pad | cell | `atb_tree.py:56-61` (atb_pad + asig_5p0) | `analog/island_support/README.md:205,224-227` | OK | series ~0.6 + 1.2 + 4.4 kOhm force / 16.4 kOhm sense; pads not in `BIND` |
| DBG_OBS0/1 mux | index map | `rtl/pt_regfile.sv:1148-1151` | `rtl/pt_digital.sv:43-45`, `spec/register-map.md:226,264` | OK | 0 tristate ... 36 rst_n |
| DBG_OBS pads | cell, OE | `pt_provider_io.sv:32-46` (bi_24t, IE=0) | `pt_chip.sv:57-58,153-156` | OK | tristate at reset |
| WDBG_OBS / WCLK_OBS | pad existence | `pt_chip.sv:18,57-58`, `pt_provider_io.sv:37-40`, `rtl/pt_regfile.sv:1147,1149,1152` | `spec/contract.json:100-102` (retired, sites now USB_DN/USB_DP), `IC:801` (PD22: wire_status -> DBG_OBS0 codes 37+n) | MISMATCH | digital half of PD22 not done: `dbg_src` is 37 entries, sel max 36 |
| CLK_OBS source select | field vs cell pins | `spec/debug-controls.json:1171-1210` (5 bits; 15/16/17 = char_ro33/ro50/cmldiv, "select = enable") | `analog/timing/clk_obs16.spice:5,15-18,28` (S3..S0 = code; 15 = OR of IN15A/B/C chosen by `debug.replica.ro33/ro50/cmldiv_enable`) | MISMATCH | those enable fields do not exist; codes 16/17 alias to S=0/1 if the low 4 bits are wired straight; no decoder cell |
| CLK_OBS inputs | binding | `BIND` clk_obs: IN0..IN15C, S0-3, N0-2, EN all `UNBOUND` | `netlist.py:94` (only OUT) | MISMATCH | |
| CLK_OBS legal sources | regfile vs bond map | `spec/debug-controls.json:1202` forbidden: wire_line, wire_sample, ref_in, aux_clk, wclk_in, host_tx_clk, cdr_recovered | `spec/contract.json:100-101` (WCLK_OBS retired) | MISMATCH | wired clocks, REF_IN and the host clock cannot be put on any clock pad |
| CLK_OBS divider | width | field `divider_log2` 4 bits, max 7 | `clk_obs16.spice:28` N0-N2 | OK | |
| CLK_OBS supply | domain | `clk_obs16.spice:20` ("always-on core rail") | `BIND` clk_obs VDD = `RAIL_debug`; field islands ["debug"] | MISMATCH (doc) | the cell's own tristate OUT then feeds the provider pad `A` (`pt_provider_io.sv:42`) |
| freq counter sources | binding | `rtl/pt_digital.sv:21-23` | `netlist.py:115-116`; `BIND` fc_src[0], [5] dangling | MISMATCH | [0] pll_tx not placed, [5] no cell |
| freq counter source rate | limit | `integration/macro-contract.md:153` (<= 156.25 MHz at the pin), `pt_digital_macro.sdc:31,205` (FC_PERIOD 6.4) | `analog/timing/README.md:139` (ring_osc 211 MHz, 165-255), `netlist.py:115` (OUT -> fc_src[2] undivided) | MISMATCH | |
| BB tap | field vs pins | `debug.bb_tap.mode` 3-bit, 8 modes (debug_cfg[27:25]) | `analog/rf_rx/bb_tap.spice:15` (`obs_en`, `inj_en`), `analog/rf_rx/README.md:155-156`; `BIND` both `UNBOUND` | MISMATCH | decoder missing |
| BB tap / WMON buffer bias | enable source | `core_bias.py:126` (`EN_bb_tap_i/q/wmon` gate the bias outputs) | `rtl/pt_digital_macro.sv:73-92` (no bb_tap or bbfilter entry in `en_eff`), `netlist.py:27-37` (no ENABLE_FIELD; bbfilter mapped to dropped `rxfilter_*.state`) | MISMATCH | `EN_EFF_bb_tap_*`, `EN_EFF_bbfilter_*` have no bits behind them |
| WMON select | field vs pins | `debug.wmon_select.select` (0 off, 1 rx_p .. 4 ctle_n) | `analog/wired_rx/wmon_sel.spice:3-6` (`wmon_en`, sel 00 = RX_P) | MISMATCH | needs en = (sel != 0), sel = code - 1; none exists; `BIND` unbound |
| WMON buffer | unused leg | `netlist.py:81-82` (`pad_n` = VSS, `in_n`/`inj_*` = `VCM_WIRE`) | `analog/rf_rx/bb_tap.spice:15`, `analog/rf_rx/README.md:114-117` (two follower legs, 0.5 mA sinks, series switch to the pad) | MISMATCH | `VCM_WIRE` has no driver; in observe mode the N-leg follower is shorted to VSS through its pad switch |
| debug-pad receivers | enables | `rtl/pt_regfile.sv:1141-1145` | `BIND` rx_aux_clk/rx_wclk_in/rx_wtx_ext EN bound | OK | `SE`, `PRESENT`, `OUTN` unbound |
| ESD_TEST | pad | `pt_chip.sv:19,53` | `spec/contract.json` bond_map_current (bidir[25] TLP site, ESD_TEST retired PD35) | MISMATCH (cosmetic) | |

---

## Findings, ranked

### DEAD MODE

**F1. `por_bypass` has no pad; a stuck POR is an unreachable die.** `integration/pt_chip.sv:44` is
`wire por_bypass=1'b0;` with the comment "OPEN at chip level: no pad is bound yet". The macro and the generator
already implement the strap (`rtl/pt_digital_macro.sv:26,96`, `rtl/gen/gen_regfile.py:512`). The POR is
third-party IP (`analog/core_support/por`) and `spec/board-requirements.md:11` already says it misses some ramps.
With `por_n` stuck low, `rst_n` is low forever, MISO never drives and no observation pad can be enabled.
No pad site is assigned in `spec/contract.json` `bond_map_current`. Related in-flight item: the regenerated
`pt_mgmt` will have a `por_bypass` port that `rtl/pt_digital.sv:51` does not connect. Owner: pads/assembly
(site + provider in_c with PD) and digital (pass-through). Reproduce: read `pt_chip.sv:40-45`.

**F3. The host link has no clock in any assembled artefact, and no decode exists to select one.**
`host_word_clk` comes only from `pt_clockmux.HOST_CLK` (`analog/timing/clockmux.spice:31`): HS_INT (TX line ring
-> `pt_prescale`) or HS_HF (ring locked to H2D_CLK). In `BIND` every clockmux, prescale and wordclk control pin is
`UNBOUND_*`, `pll_tx` is in `floorplan.json` `failures`, and `digital.host_word_clk` is alone on its net. The
select pins are one-hot (`HS_INT`, `HS_HF`, `PS_H2D`, prescale `D2..D16`) while the register file exports the
3-bit enum `debug.clk_select.host_clk` and `clocktree.config.*` raw; the hardened macro has no decoded outputs
for them and there is no glue-decode cell in `verification/chip_assembly/inventory.py`. The ring enable has the
same problem: `netlist.py:36` keys `pll_tx` to `wirepll.state.state`, a dropped field. D2H and H2D both need this
clock (`rtl/pt_digital_macro.sv:138`), so both directions are dead until someone owns the decode. Reproduce:
`python3 -c "import json;b=json.load(open('scratch/integration/m6-powerup/chipnet/binding.json'));print(b['bindings']['clockmux'])"`.
Owner: timing (decode cell or a spec for it) + digital (if the decode moves into the macro) + assembly.

**F4. host_follow cannot work: H2D_CLK never reaches the clock mux.** `clockmux.spice:23,27` has the `H2D`
input and `PS_H2D` select; `pt_analog_physical` (`integration/pt_chip.sv:119-148`) has no h2d_clk port, and
`pt_chip.sv:48,65` routes the pad Y only to the macro. host_follow is the stated host/converter clock for
passive-LO RF mode (`spec/debug-controls.json` debug.clk_select description). Owner: integration (port) + timing.

**F5. BB_I/BB_Q and WMON observation have no enable path.** The three `pt_bb_tap` instances need
`obs_en`/`inj_en` (decoded from the 3-bit `debug.bb_tap.mode` / `debug.wmon_select.select`) and a bias enable
`EN_bb_tap_*` on core_bias (`integration/core_bias.py:126`). Neither exists: `en_eff[19:0]`
(`rtl/pt_digital_macro.sv:73-92`) has no bb_tap or bbfilter entry, `netlist.py:27-37` has no enable field for
them (bbfilter is mapped to the dropped `rxfilter_*.state`), and `pt_wmon_sel` needs `wmon_en` + a code-1 select
(`analog/wired_rx/wmon_sel.spice:3-6`). Separately, `netlist.py:81-82` ties the WMON buffer's unused leg to VSS
with its input on `VCM_WIRE`, a net with no driver. These are three of the four analog fallback routes
(`rf_bb_external_adc`, `wire_wmon_scope`, ...). Owner: rf_rx (decode spec), digital (en_eff), assembly.

### DEGRADED

**F2. The hardened macro is stale against the RTL.** RTL: analog_cfg 579, debug_cfg 256, ATB 58, plus
`wire_rx_ptrim_en` and `rf_tx_clk_out` (`rtl/pt_regmap_defs.svh:2-4`, `rtl/pt_digital_macro.sv:43,49`). Newest
abstract on disk (`R4LEF`, 2026-11-11): 568 / 255 / 57, neither new pin. The assembly's default abstract
(`scratch/digital-outline/pt_digital_macro.lef`, `inventory.py:22`) is older still (513 / 243, 20-bit wired
buses). Missing bits include `lna.match.att` top, `pllvreg.config.*` (analog_cfg[577:578]),
`debug.calibration.valid` (debug_cfg[255]) and ATB code 58. `evidence/digital-hardening-evidence.json` is run
CLOSE_R2: 27 of its hashed sources are stale or deleted, its MAP_HASH is 0x179e (current 0x2c7c), yet it records
`hardened_rtl_matches_current: true`. Timing is not closed (`scratch/digital-timing-close/NOTES.md`, TC2A).
Reproduce: count `PIN analog_cfg` in the LEFs. Owner: digital.

**F6. D2H launch is in the macro but the floorplan still assumes a south pad-edge gearbox.** `IC:312` accepted
"word/4 crosses the corridor"; `inventory.py:482-486` reserves `rsv_d2h_gearbox` and labels the corridor "D2H
word/4". The RTL launches DDR inside the macro (`rtl/pt_host_link.sv:107-121`), so eleven 3.2 ns-UI lanes cross
2.7 mm+ unbuffered with only a prose length-matching request (`IC:908`). The reserve contains no cell. Reduced
rates (/2, /4) and FPGA per-bit training are the mitigation. Owner: assembly + digital (decide: repeater/retime
cell in the reserve, or accept and constrain).

**F7. PD22 observation folding was done on the pad side only.** WCLK_OBS and WDBG_OBS sites are now USB
(`spec/contract.json:100-102`), but `pt_chip.sv:18`, `pt_provider_io.sv:37-40` and the register file still carry
them; `dbg_src` was not extended to 37+n (`rtl/pt_regfile.sv:1148`), and `debug.clk_obs.source` still forbids
wire_line, wire_sample, wclk_in, cdr_recovered, ref_in, aux_clk and host_tx_clk
(`spec/debug-controls.json:1202`). Net effect on die 1 as specified: none of the 16 `wire_status` bits and none
of the wired/reference/host clocks can reach a pad. Owner: digital (PD22 row), then assembly for IN2/3/7/13/14.

**F8. CLK_OBS select encoding disagrees between field and cell.** Field: 5 bits, codes 15/16/17 select and
enable the three characterization oscillators. Cell: S3..S0 only, code 15 = OR of three inputs gated by enable
fields that do not exist (`analog/timing/clk_obs16.spice:15-18`). All 26 input/select pins are unbound and the
characterization cells are not in the inventory. Owner: timing + digital (one decoder, or change the field).

**F9. ATB: characterization and several block nodes lead nowhere; island nodes ignore pgood_override.**
Codes 43-54 (no `pt_char_*` instance), 58 (no leaf, no macro bit), 4, 15, 23, 25, 27, 30, 31, 32, 34, 36, 41
(unbound), and 2 (leaf on a driverless net). The reference chain, VBG and all rails are fine. Independently,
`rtl/pt_regfile.sv:1029-1056` gates island leaves with the raw `island_pgood`, so the pgood_override fallback
removes ATB access to exactly the island whose detector failed. Owner: assembly (bindings), characterization
(placement), digital (gate with `island_on` only).

**F10. Status and fault inputs without a source.** `fault` (no monitor block anywhere; forces all TX outputs off
if it floats high, `rtl/pt_regfile.sv:444-729`), `analog_status[2]` bias_ready, `[11]` aosc_div, `[1]`
ref_present and `ref_clk` itself (no REF_IN receiver instance; the net joins two inputs), `island_pgood[3]`.
`ref_clk` also runs `pt_vreg_seq` (`rtl/pt_digital_macro.sv:174`), which gates both ring enables. Owner:
integration (tie-offs), timing (REF receiver), spec (retire monitor fields: 75 analog_cfg bits with no consumer).

**F11. `island_on[0]` still has two drivers in the netlist.** `netlist.py:128` vs `rtl/pt_digital_macro.sv:188`;
`pt_chip.sv:74` ties `wired_on_ext` to 0 instead of taking `WIRED_ON`. Owner: assembly + integration.

**F12. Macro clock inputs from the pll island are not in the isolation plan.** No `iso_clamp_x4` entry for
HOST_CLK -> `host_word_clk` or for `ref_clk` in `scratch/iso-family/publish/iso-placement.json`; both float in
the SPI-only state. Owner: pads/assembly.

**F13. ring_osc drives `fc_src[2]` at 165-255 MHz** against a 156.25 MHz pin limit
(`integration/macro-contract.md:153`, `analog/timing/README.md:139`, `netlist.py:115`). Owner: timing (divide)
or digital (constrain at 3.9 ns).

**F14. D2H reset-default pad setting is below full rate** (drive 1, slow slew: 141 MHz @5 pF tt). Owner:
digital (defaults) or FPGA plan (bring-up step).

### COSMETIC

- `sim/tb_chip_io.sv:68` reads RESET_STATUS at 0x08; the only chip-level digital bench therefore fails.
- `integration/macro-contract.md:53-54` says 509 / 107.
- `spec/fpga-connection-plan.md` budgets RX2 / `hostio.lane_dir`, which is in no RTL, map or pad binding.
- Legacy macro ports (`enable`, `mode8`, `rf_trim`, `wire_trim`, `clock_trim`, `calibration_*`: 63 pins) have no
  analog consumer; `en_eff[11]` is still keyed to `rfpll.state` for the dropped `pll_host`.
- `ESD_TEST` still a `pt_chip` port; `clk_obs16.spice:20` says "always-on core rail" but sits on RAIL_debug.
- `pt_chip.sv:81` (`sclk&cs_n`) and `:45` need glue cells that nobody owns.
- RESET_N: open-drain supervisor (B1) plus on-chip pull-down needs a stated board pull-up value.

## Could not trace

- Any physical route (SPI, RESET_N, D2H, H2D, DBG/CLK_OBS, ATB pads to the tree): no chip-level netlist
  contains the provider ring cells, and no routed top exists. The SPI path is verified only in Verilog with
  functional pad models.
- Transistor-level behaviour of provider pads with a floating `A` (clk_obs16 tristate output into bi_24t) or
  floating inputs; pull-down strength of in_c.
- Whether a hardened macro newer than AC1_R4 exists outside `scratch/` (none found newer than 2026-11-11 01:46).
- Host-link timing at the pads (macro STA not closed; no pad + route model); SCLK edge rate at the macro pin.
- The clock/data content of the transport (pt_quad_link / pt_core framing) against an FPGA implementation:
  no FPGA gateware in the tree to compare with; block benches only.
- ADC/CDR/PLL status bits ([0], [5]-[10], wire_analog_status[12:0]) beyond noting they are all undriven in
  `BIND`; the owning cells have the pins (LOCK, DONE, OVERLOAD, READY, PRESENT) but no binding rule.
- ATB force capability against each bias node's impedance (series resistance figures quoted from
  `analog/island_support/README.md:224-227`, not re-simulated).
