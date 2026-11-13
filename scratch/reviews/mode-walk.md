# End-to-end mode walk: cross-block interface mismatches (independent chip-level review, 2026-11-13)

Scope: every user-facing mode traced pad to pad (signal, clock, bias/reference, enable/config) through the
actual artefacts: block `.spice` pin lists and internals, generated LVS/extracted netlists, `rtl/*.sv`,
`rtl/pt_regmap_defs.svh` / `spec/register-map.json`, `integration/pt_chip.sv`, and the only chip-level netlist
generator (`verification/chip_assembly/netlist.py` + `inventory.py`; fresh output of today in
`scratch/integration/m6-powerup/chipnet/binding.json`, called BIND below). READMEs were used only to locate
things. No design file was modified. Paths are relative to `projects/programmable_transceiver_platform/` unless
they start with `scratch/`. `IC` = `scratch/reviews/interface-changes.md`.

Work directory: `scratch/reviews/mode-walk/` (scripts, decks, logs, and the four detailed part reports
`part-rf.md`, `part-wrx.md`, `part-wtx-clk.md`, `part-dig.md`, whose boundary tables are reproduced in section 6).

## 1. Bottom line

**No payload mode can run from the artefacts as they stand. Only SPI register access closes end to end, and
that only at RTL level with functional pad models.** The reason is structural rather than one bug:

1. **The analog top does not exist.** `pt_analog_physical` is a black box (`integration/pt_chip.sv:119-148`).
   The only chip netlist binds 2892 ports of which **653 are unbound** and **1170 nets dangle**, including every
   digital datapath bus (`wire_rx_data`, `wire_tx_data`, `rf_rx_sample`, `rf_tx_sample`, all five payload
   clocks) and 559 of 579 `analog_cfg` bits. **14 blocks of the v6 floorplan have no instance in any netlist**
   (qvco, lo_mmd, lo_pfdcp, lo_lf, lo_obs, cdr, pll_tx, pll_vreg2, ptrim, vthdac, wrx_cap, obs_pre4,
   term_buffer, lo_mmd_qdum). So nobody has ever had to make two neighbours agree.
2. **The register map was last trimmed against the cells of 2026-11-09/11 and the cells have moved on.**
   39 control-pin groups on current cells have no register field, 12 more have the wrong width, and 80 bus
   fields (397 bits) have neither an RTL reader nor a cell pin (`cfg_map.py`). Dozens of "digital: add field
   X" rows in IC were never implemented.
3. **Nothing owns the glue between the two.** One-hot/thermometer cell selects (clockmux, prescale, wordclk,
   lo_ext, termination, rxlevel, wmon, bb_tap, clk_obs) face raw binary fields with no decoder cell. The
   macro's own decode outputs (`en_eff[19:0]`, `island_off`, `wire_rx_ptrim_en`, `rf_tx_clk_out`) are not
   connected at chip top (verilator PINMISSING at `integration/pt_chip.sv:64`), and `pt_analog_physical`
   has no ports for them.

Beyond "not wired yet", the walk found mismatches that **survive perfect wiring**, because the two sides were
verified against different assumptions. The ones with numbers:

| What | Bench assumed | Neighbour actually presents | Effect (reviewer sim) |
|---|---|---|---|
| RX mixer LO | 0/VDD square | `pt_lo_ext` sine, peak Vgs 0.9-1.16 V | conversion gain -4.6 to -16.2 dB vs bench (tt, quad only) |
| CTLE load | 150 fF per leg | rxselect TG + ~0.66 pF slicer + wmon_sel | 1.25 GHz gain +2.1 dB -> -8.0 dB; -3 dB BW 1.82 GHz -> 248 MHz (tt, extracted chain) |
| ptrim load | 150 fF per phase | ~1.0 pF on CKP0, 0.45-0.6 pF on CKP1..7 (estimate +/-30 %) | CKP0 0.48-2.88 V, 638 ps rise, 96 ps lag (> 89 ps trim range) at 625 MHz tt |
| Serializer phase inputs | full-rail phases | ring on 0.9 x rail (2.57-3.01 V), no level restore | 15-50 ps less window per 400 ps UI (estimate) |
| CTLE output CM | slicer benched at 1.0 V | 1.47 V tt, 1.52-1.66 V ss | unqualified operating point (function check passes, 15 % less sampler current) |
| ADC/DAC clock | 0.4 V differential about 1.65 V, shaped high time | one single-ended CMOS `CONV_CLK` | not simulated; acquisition = clock high time, no shaper exists |

### Mode status

| Mode | Runs from current artefacts? | First blockers (finding IDs, section 3) |
|---|---|---|
| 2.4 GHz RX narrowband | No | MW-1, MW-2, MW-3, MW-4, MW-5, MW-6, MW-7, MW-20 |
| 2.4 GHz TX | No | MW-1, MW-2, MW-3, MW-4 (filtered path), MW-7, MW-21 |
| Duplex TX+RX | No | all of RX and TX, plus MW-22 (one CONV_CLK, no lobias/hib bits) |
| Wired RX, low rate | No | MW-8, MW-9, MW-10, MW-11, MW-12 |
| Wired RX, top rate | No | same, plus MW-13 (CTLE load), MW-14 (ptrim load), MW-23 (no evidence > 2.5 Gb/s) |
| Wired TX, CMOS path | No | MW-2, MW-15, MW-16, MW-17 |
| Wired TX, CML path | No (hardware does not exist) | MW-24 |
| USB | No (no data path either direction) | MW-18 |
| 100BASE-TX | No | RX: MW-8..12 + MW-25; TX: MW-15..17 + POST_POL (MW-25) |
| Host link D2H / H2D | No (no host clock, nothing can select one) | MW-2, MW-19 |
| SPI-only bring-up | **Yes at RTL level** (pad models; `CHIP_IO_PASS` after fixing a stale bench address) | risk: MW-26 (por_bypass unbonded), MW-27 (stale hardened macro) |
| ATB / debug observation | Partly: reference chain, VBG, rails OK | MW-28 (25 dead ATB codes), MW-29 (BB tap / WMON / CLK_OBS have no enable path) |

## 2. Mechanical checks (scripts, each with a must-fail self-test)

All in `scratch/reviews/mode-walk/`. Run `python3 <script> --selftest` then `python3 <script>`.

| Script | What it checks | Self-test (injected mismatch) | Result on the real design |
|---|---|---|---|
| `pins.py` | collects every `.subckt` pin list under `analog/` with file:line into `pins.json` | n/a (data) | 671 subckts |
| `top_pins.py` | A: each instance in `pt_chip_full` has as many nets as its subckt has pins. B: extracted library pin set == schematic source pin set. C: `netlist.py` binding rules that name a pin or instance that does not exist. D: v6 floorplan blocks with no netlist instance. E: unbound/dangling census | drops a net from `Xlna`, renames a `pt_txsum` pin, adds a bogus rule: all three reported | A: clean. B: `pt_cdr` schematic has `otr0..4, otrs`, layout/extraction does not. C: 3 rules to removed `pt_wiredtx` TMDS pins; 14 rules to instances that are not in the netlist (pll_tx, pll_host, cdr, wclk_obs). D: 14 blocks. E: 653 unbound, 1170 dangling |
| `cfg_map.py` | register field -> cell control pin table (from the owners' README tables): pins with no field, width mismatches, bus fields with no RTL reader and no pin | narrows `lna.match.att` to 4 bits, deletes `rfdriver.mute.mute`: both reported | 39 pin groups with no field, 12 width mismatches, 80 orphan fields / 397 bits (`cfg_map.out`) |
| `bias_sum.py` | every bias pin of every chip cell: direction (must end on an NMOS diode, since the banks source 10 uA) and existence of a `core_bias` output | PMOS-diode consumer and consumer missing from `CONSUMERS`: both reported | Direction and magnitude agree everywhere (23 x 10 uA sourced, all consumers sink into NMOS diodes). **No output for `pt_cdr.IBIAS`, `pt_lo_pfdcp.IBIAS`, `pt_wtx_hsbias.IBIAS`; the QVCO output is fabricated with EN tied low (`integration/core_bias.py:123-128`); `pt_lna.lobias` has no source.** The deleted pll_host leaves one spare PLL-bank output |
| verilator lint of `integration/pt_chip.sv` + `rtl/pt_*.sv` | port/width agreement at chip top | n/a (tool) | no width errors; PINMISSING `rf_tx_clk_out`, `wire_rx_ptrim_en`, `en_eff`, `island_off` at `pt_chip.sv:64` |

Reviewer sims (decks and logs kept): `rf/mixlo.py` (mixer vs LO waveform), `wrx/ctle_*_{bench,chain}.cir`,
`wrx/ptrim_load.cir`, `wrx/pincap.py`, `wrx/op_*.cir`, `wrx/sl_sch_*.cir`, `wtx/phswing.py`,
`dig/tb_chip_io_local.sv`.

## 3. Findings, ranked

Severity: **DEAD** = the mode cannot work even if everything else is wired as the owners intend, or a needed
function exists nowhere. **DEGRADED** = works but misses its numbers, or is unverified at the real operating
point. **COSMETIC** = stale text or dead bits. Each finding names both sides. "Assembly rule" findings are
errors in `netlist.py`, which is the only statement of intended chip connectivity.

### DEAD

| ID | Finding | Side A | Side B | Reproduce | Owner |
|---|---|---|---|---|---|
| MW-1 | **The mixer LO cannot be switched on.** `pt_lo_ext` clamps the LO nodes to VSS unless EXT/INT/CMLSEL is set; no register field drives them (`consolidation.quadrature.mode` was dropped; LO17 `rfpll.config.lo_cmlsel` never added) | `analog/timing/lo_ext.spice:19-20,97-99` | `spec/register-map.json` (quadrature.* bus = null); BIND `lo_ext.EXT/INT/CMLSEL` unbound | `python3 cfg_map.py` (pt_lo_ext rows) | digital + timing |
| MW-2 | **No clock selection anywhere.** `pt_clockmux` has 16 one-hot selects, `pt_prescale` D2..D16, `pt_wordclk` D10/D20; the register file exports binary enums and there is no decoder cell. `ref_clk` has loads and no driver (no `pt_diff_clk_rx` instance on REF_IN). `host_word_clk`, `CONV_CLK`, wire clocks have no source in BIND | `analog/timing/clockmux.spice:23-31` | `rtl/pt_digital_macro.sv:94` (only `en_eff`); `verification/chip_assembly/inventory.py:309-310`; BIND clockmux 30/32 unbound | `python3 top_pins.py` section E | timing + digital + assembly |
| MW-3 | **Converter clock/data glue does not exist.** ADC/DAC benched with a 0.4 V differential clock about 1.65 V and a shaped high time (ADC acquisition = clock high time); the clockmux gives one single-ended CMOS `CONV_CLK`. `rf_rx_clk`, `rf_tx_clk`, `rf_rx_valid`, `rf_tx_request` have no producer; `rf_tx_clk_out` unconnected; `ILEN` has no bit; `CODEB/DONEB` have no consumer; DT-6 wants falling-edge capture, the DAC captures on rising | `analog/converters/benches.py:193-197,524-525`; `analog/converters/rtl/dac_logic.v:22` | `analog/timing/clockmux.spice:3,30`; `integration/pt_chip.sv:64-85`; IC:1011 | BIND `adc_i.CLKP` etc. unbound | timing (converter clock cell) + converters + digital |
| MW-4 | **Shared bbfilter: no enable and incompatible codes.** No `en`/`dir_tx` decode (`en_eff` has no bbfilter bit; `netlist.py` keys it on the dropped `rxfilter_i.state`), so its bias bank never turns on. Gain: cell wants 6+2 bits through a 17-entry LUT with all-zero = muted; map has 4 linear bits, reset 0 (= muted, max +11.5 dB instead of +42 dB). bw 7 bits/reset 8 vs 4 bits/reset 0; qt 4 bits/reset 6 vs 2 bits/reset 1 (violates the cell's own "cap code <= 1 needs qt >= 6"). `dcf[8:0]`, `fc_fine`, `gainc` have no bits. One field set drives both I and Q | `analog/rf_rx/bbfilter_i.spice:796`; `analog/rf_rx/README.md:98,140-158`; IC:153-160 | `rtl/pt_regmap_defs.svh:90-91`; `rtl/pt_digital_macro.sv:73-92`; `verification/chip_assembly/netlist.py:30` | `python3 cfg_map.py` | digital + rf_rx |
| MW-5 | **Current LNA is not integrated.** `src_p/n` (downbond pads) and `tank_p/n` (spirals "placed at assembly") have no pad/cell in the inventory. Assembly rule puts both mixers on `rf_out` and leaves `rf_outq` open; the chain bench uses one output per mixer | `analog/rf_rx/lna.spice:8`; `analog/rf_rx/tb.py:889,893-894` | `verification/chip_assembly/netlist.py:57-58`; BIND `lna.rf_outq_p` unbound | BIND lookup | assembly + pads + rf_rx |
| MW-6 | **Converter references not connected (assembly rule).** `core_bias.VREF0/VCM` land on `ATBN_master_*`; `refbuf.VREF0` and `adc_*.VCM` sit on `VREF0_CONV`/`VCM_CONV` with only ATB leaves. VCM is used in every conversion. Refpad `VCM` has no driver either | `integration/core_bias.py:82,133,144` | `verification/chip_assembly/netlist.py:53,64-65`; `analog/converters/rtl/adc_sar_logic.v:32,92` | BIND `core_bias.VREF0` vs `refbuf.VREF0` | assembly |
| MW-7 | **On-chip LO synthesizer is not on the chip.** QVCO/lo_mmd/lo_pfdcp/lo_lf are laid out but not in `inventory.py`; all `rfpll.config.*` fields are dropped (MMD N[5:0], ICP[1:0], BAND[3:0], PRE have no bits); QVCO bias output EN tied low; no bias output for lo_pfdcp. Known as LO3; listed so nobody plans on it. External LO (B3) is then the only LO, and it occupies REF_IN and AUX_CLK, leaving H2D_CLK as the only reference for sample/host clocks (MW-2, MW-19) | `analog/timing/lo_mmd.spice:228`, `lo_pfdcp.spice:24`, `lcvco/qvco5.spice:12` | `integration/core_bias.py:123-128`; register-map trim "unified into consolidation.pll" | `python3 bias_sum.py`; `python3 cfg_map.py` | timing + coordinator |
| MW-8 | **HS receive pair is wired to nothing; the CTLE listens to the USB pins (assembly rule).** | `analog/wired_rx/README.md:788-794` (HS_RX -> ctle only) | `verification/chip_assembly/netlist.py:96,131-133`; BIND `pad_hs_rx.RX_P` unbound | BIND lookup | assembly |
| MW-9 | **No register for HS pad bias/termination.** `hs_en`, `hs_term_en`, `hs_trim[3:0]`, `term_en` have no field (PD27 asked for `termination.config.trim[3:0]` reset 5). With `hs_en=0` HS_VBIAS is grounded: CTLE input at 0 V, below its ~0.8 V window | `analog/wired_rx/termination.spice:6-8,11` | `rtl/pt_regmap_defs.svh` (only DIFFERENTIAL_100_ENABLE, P_LOAD); IC:806 | `python3 cfg_map.py` | digital |
| MW-10 | **CDR control plane missing from the hardened RTL.** Analog expects FUP/FDN pulses, `pfd_mode`, `ref_sel`, KP[2:0], N5/N10, capture B2/B1, PSEL[2:0], SLIPP/SLIPM, EN; the macro exports only `cdr_freq_locked`. `analog/wired_rx/rtl/pt_wrx_cdr_loop.sv` is not instantiated and targets retired pins. The loop cannot acquire without the FLL (P path alone fails at +3000 ppm; every closed-loop bench presets VCTRL). Full-rate modes have no analog phase detector | `analog/wired_rx/cdr.spice:6-7,22`; `analog/wired_rx/sims.py:1212`; `analog/wired_rx/capture.py:438-439` | `rtl/pt_digital_macro.sv:25-75`; `grep -rn pt_wrx_cdr_loop rtl/ integration/` (nothing) | grep | digital + wired RX |
| MW-11 | **Capture has no word-restart (LDE) source.** `pt_wrx_cap` needs one LDE per 20 bits synchronous to the RX ring; there is one `pt_wordclk`, bound to the TX net, with CK/LDE/D10/D20 unbound. RX and TX rings run at different frequencies | `analog/wired_rx/capture.py:210-211,655-661` | `verification/chip_assembly/inventory.py:293`; `verification/chip_assembly/netlist.py:114` | BIND `wordclk` | timing + assembly |
| MW-12 | **`wire_rx_valid`, `wire_tx_request` and wired status bits have no producer.** The core drops every RX quad unless valid is high, and repeats one TX word forever unless request is high; no analog cell has such a pin | `rtl/pt_core.sv:87,227` | `analog/wired_rx/generated/wrx_cap.lvs.spice:4707`; `analog/wired_tx/wiredtx.spice:1124` | pin lists in `pins.json` | digital + assembly |
| MW-15 | **`SER_EN` can never assert.** Assembly binds it to `ct_ser_run`, set only after an armed, qualified, marker-triggered launch that needs `ct_ref_clk` (no driver) with a period of exactly 10 or 5 `ct_wclk` cycles; every analog divider is a power of two, and the serializer has its own /5 and /2. `ser_run` never clears. Result: `WORD_CLK40` / `wire_tx_clk` never toggle. The clock-tree RTL models a serializer that no longer exists | `rtl/pt_clocktree_slow.sv:134,153,169` | `verification/chip_assembly/netlist.py:109`; `analog/wired_tx/wiredtx.spice:1130,1171-1173`; `analog/wired_tx/README.md:179` | `grep -n ser_run rtl/pt_clocktree_slow.sv` | digital + wired TX |
| MW-16 | **TX ring: no instance, no agreed enable, no band bit.** `pll_tx` failed placement and is in no netlist; assembly enables it from the dropped `wirepll.state` while RTL `en_eff[11]` (still named pll_host) uses `rfpll.state`; `BAND` is tied high with no register bit, and the high-band floor is 484 MHz at ff, so ring 371.25 / 375 / 405 MHz (TMDS 1.485, SATA 1.5, DP 1.62) have no legal setting; N = 4/8/16 only and the reference divider was dropped, so each rate needs its own board reference | `analog/timing/pll_ring_core.spice:3,38`; IC:974 | `verification/chip_assembly/netlist.py:36-37,121`; `rtl/pt_digital_macro.sv:84,178` | `python3 top_pins.py` (C2, D) | digital + timing + board spec |
| MW-17 | **TX pad TMDS branch floats in every mode; WTX_EXT fallback cannot be built.** Pad `TMDS_P/N/TMDS_BIAS` are bound to pins removed from `pt_wiredtx` (gate of a 16 x 20/1 um tail on WIRE_TX undriven). `integration/wtx_fallback.py` connects the same removed pins (fixture raises), requests the TMDS branch where EN_MAIN is now needed, and the assembly shorts `rx_wtx_ext.OUTP` onto the `WTX_EXT_DATA` output with `DX` unbound | `analog/pads/generated/wired-transmit-lifecycle.spice:8` | `analog/wired_tx/wiredtx.spice:1124`; `verification/chip_assembly/netlist.py:90,106-108,135-136`; `integration/wtx_fallback.py:108,139-146` | `python3 top_pins.py` (C) | pads + wired TX + assembly |
| MW-18 | **USB has no data path in either direction.** Pad pins `HS_P/N`, `FS_HIGH/LOW_P/N` have no driver; no USB logic or port in RTL; chip top has no USB_DP/DN (ports predate PD22); `pt_detect` outputs have no consumer. Static pull/trim/hsbias fields do match; `pt_wtx_hsbias.IBIAS` has no bias output | `analog/pads/generated/wired-receive-usb-lifecycle.spice:6` | `integration/pt_chip.sv:11-21`; `grep -il usb rtl/*.sv` (nothing) | grep | coordinator, then digital + pads |
| MW-19 | **Host link has no clock and host_follow cannot work.** `host_word_clk` comes only from `clockmux.HOST_CLK` (TX ring or host_follow); `clockmux.H2D` exists but `pt_analog_physical` has no h2d_clk port, so the pad clock reaches only the macro. Both directions need this clock. In RF modes the regfile rule `rf_wired_payload_exclusive` also forbids `cdr.state` active while an ADC/DAC/LNA is active, so the CDR ring cannot be the host-follow ring | `analog/timing/clockmux.spice:12-16,23,27` | `integration/pt_chip.sv:48,65,119-148`; `rtl/pt_regfile.sv:1178` | BIND net `host_word_clk` (one pin) | integration + timing + digital |
| MW-24 | **Wired TX 2.7-3.24 Gb/s (CML path) does not exist as hardware.** `pt_wiredtx` is the all-CMOS quarter-rate `wtx_serq4c`; rate plan capped at 2.5 Gb/s; the CML pre-driver is scratch-only with a NO-GO review; the published cells also fail 2.0-2.5 Gb/s at the pad in the owner's WT24 bench | `analog/wired_tx/wiredtx.spice:974-1010` | IC:224,227,1193; MANDATE "final 2:1 is CML" | read | wired TX |
| MW-25 | **100BASE-TX has no digital half.** No fields for `vthdac` A/B/`vth_en`, slicer `vsel`, CTLE `lf_zero`, `POST_POL`; no IX-11 fast-threshold opcode (only opcode 4); no edge-word input on the macro; `vthdac` not in the inventory. The analog cells agree with each other | `analog/wired_rx/vthdac.spice:8`; `analog/wired_rx/slicer.spice:11`; `analog/wired_tx/wiredtx.spice:1124` | `rtl/pt_core.sv:270-279`; `rtl/pt_regmap_defs.svh`; IC:217,781,1055 | `python3 cfg_map.py` | digital |

### DEGRADED

| ID | Finding | Side A | Side B | Reproduce | Owner |
|---|---|---|---|---|---|
| MW-13 | **CTLE bandwidth collapses with its real load** (may be a dead top rate). Extracted ctle -> rxselect -> slicer, tt: -8.0 dB at 1.25 GHz (bench +2.1), -3 dB at 248 MHz (bench 1.82 GHz); peak code 7 does not recover it. One corner, reviewer's chain deck | `analog/wired_rx/sims.py:232-233` (150 fF) | extracted `rxselect` + `slicer` (~0.66 pF per leg) | `cd scratch/reviews/mode-walk/wrx && ngspice -b ctle_0_chain.cir` vs `ctle_0_bench.cir` | wired RX |
| MW-14 | **No verified clock path ring -> ptrim -> samplers/capture.** ptrim benched with 150 fF; real loads ~1.0 pF (CKP0) and 0.45-0.6 pF (load is an estimate, +/-30 %). At 625 MHz tt CKP0 does not reach the rails and lags 96 ps. Slicer and capture were only benched with ideal clocks; ptrim's published layout is called unusable by its owner and is in no netlist | `analog/wired_rx/sims.py:718` | `analog/wired_rx/generated/slicer.ext.spice`, `wrx_cap.ext.spice` | `ngspice -b ptrim_load.cir`; `python3 pincap.py` | wired RX |
| MW-20 | **RX mixer under-driven by the real LO.** Benches use a 0/VDD square; `pt_lo_ext` delivers a sine with peak Vgs >= 0.9 V as its pass criterion. Conversion vs bench: -4.6 dB (1.16 V), -7.3 dB (1.05 V), -16.2 dB (0.90 V); tt, quad only | `analog/rf_rx/tb.py:453,867,1076,1226` | `analog/timing/lo_ext_pad.py:258` | `python3 scratch/reviews/mode-walk/rf/mixlo.py` | rf_rx + timing |
| MW-21 | **TX chain interfaces benched off-nominal.** TX mixer only benched with 0/3.3 V and 0/2.5 V square LO (not simulated here). DAC into the shared filter benched at 0.2 V of ~0.98 V full scale through an NMOS-only switch, with a 100 fF capacitive DAC bench load. `rfdriver.mute` has two sources (`rf_mute` from the core and the register bit) and no gate | `analog/rf_tx/simulate.py:116-122`; `analog/rf_rx/tb.py:1006`; `analog/converters/benches.py:324` | `analog/timing/lo_ext.spice`; `analog/rf_rx/bbfilter_i.spice:769`; `rtl/pt_core.sv:261` | read | rf_tx + rf_rx + converters + digital |
| MW-22 | **Duplex.** One `CONV_CLK` for ADC and DAC (80 MS/s halfband TX with a 40 MS/s ADC is impossible); `lna.lobias` and rxmix `hib` have no register bits, so the RC-16k duplex current reduction cannot be enforced | `analog/timing/clockmux.spice:30`; `analog/rf_rx/lna.spice:8` | `rtl/pt_digital.sv:89-95`; IC RC-16k | `python3 cfg_map.py` | timing + digital |
| MW-23 | **No passing evidence chain above 2.5 Gb/s on RX**, and CTLE output CM (1.47 V tt, 1.52-1.66 V ss) is outside what the slicer was qualified at (1.0 V). Function check passes at the high CM with 15 % less sampler current; sensitivity unknown | `analog/wired_rx/ctle.spice:2` ("~1.0 V"); IC:1054 | `analog/wired_rx/sims.py:455`; `analog/wired_rx/generated/wrx_cap-evidence.json` | `wrx/op_*.cir`, `wrx/sl_sch_*.cir` | wired RX + coordinator |
| MW-26 | **`por_bypass` strap has no pad** (known open DT-10, restated because it is the one item that can make die 1 unreachable): tied `1'b0` at chip top; a POR that never releases holds `rst_n` low forever. An in-flight generator edit adds a `por_bypass` port to `pt_mgmt` that `pt_digital.sv` does not connect | `integration/pt_chip.sv:44` | `rtl/pt_digital_macro.sv:26,96`; `rtl/gen/gen_regfile.py:512,849`; `rtl/pt_digital.sv:51` | read | pads/assembly + digital |
| MW-27 | **Hardened macro is stale against the RTL.** RTL: analog_cfg 579, debug_cfg 256, ATB 58, plus `wire_rx_ptrim_en`, `rf_tx_clk_out`. Newest LEF (AC1_R4, 11-11): 568 / 255 / 57, neither pin. Assembly default abstract: 513 / 243 with 20-bit wired buses. `evidence/digital-hardening-evidence.json` (CLOSE_R2) records `hardened_rtl_matches_current: true` with a different map hash and ss setup slack -7.4 / -12.3 ns in the wired TX domain. `integration/macro-contract.md:53-54` says 509 / 107 | `rtl/pt_regmap_defs.svh:2-4`; `rtl/pt_digital_macro.sv:43,49` | `scratch/integration/m6-powerup/chipnet/digital.json`; `verification/chip_assembly/inventory.py:22` | diff pin counts | digital |
| MW-28 | **ATB: 25 codes dead.** 43-54 (no `pt_char_*` in the inventory), 58, 4, 15, 23, 25, 27, 30, 31, 32, 34, 36, 41 (unbound), 2 (leaf on a driverless net). Island leaves are gated by raw `island_pgood`, so `pgood_override` does not restore ATB access to the island whose detector failed. Reference chain, VBG and all rails are fine | `spec/debug-controls.json` atb_nodes | BIND unbound `atb*_leaf*.NODE`; `rtl/pt_regfile.sv:1029-1056` | BIND `unbound` list | assembly + digital + characterization |
| MW-29 | **Observation paths with no enable or with one-sided changes.** `pt_bb_tap` obs_en/inj_en and its bias enable have no decode; assembly puts the tap on the ADC input/DAC output nets instead of the filter `obs`/`inj` pins. `pt_wmon_sel` has no enable/select decode and its buffer input sits on a driverless `VCM_WIRE`. CLK_OBS: 5-bit field with codes 15-17 vs a 4-select cell; all inputs unbound. PD22 folding (WCLK_OBS/WDBG_OBS -> CLK_OBS/DBG_OBS) was done on the pad side only: no wire_status bit and no wired/reference/host clock can reach a pad | `analog/rf_rx/bb_tap.spice:15`; `analog/wired_rx/wmon_sel.spice:3-6`; `analog/timing/clk_obs16.spice:5,15-18` | `verification/chip_assembly/netlist.py:79-82`; `rtl/pt_regfile.sv:1148`; `spec/debug-controls.json:1202`; `integration/pt_chip.sv:18` | `python3 cfg_map.py` | digital + assembly + rf_rx |
| MW-30 | **Bias outputs missing for `pt_cdr.IBIAS`, `pt_lo_pfdcp.IBIAS`, `pt_wtx_hsbias.IBIAS`; `cdr.IB_PLL` (meant for the ring's IBIAS) competes with `BIAS_pll_ring_rx` in the assembly rule; stale `cdr` bindings (`FBCK_IN`, `freq_hold` no longer exist; `cdr.VCTRL` on a net the ring is not on; `pll_cdr.REF` from `ref_clk` instead of `cdr.REF_PLL`)** | `analog/wired_rx/cdr.spice:22,51,58` | `integration/core_bias.py:14-20`; `verification/chip_assembly/netlist.py:113,122` | `python3 bias_sum.py`; `python3 top_pins.py` | assembly + bias |
| MW-31 | **Rings verified on a regulator the netlist lacks, and into a rail they do not swing to.** `pll_vreg2` is in no inventory; BIND puts `pll_cdr.VDD` on `RAIL_pll`. With the regulator, phases are 2.57-3.01 V into the 3.3 V serializer with no level restore (15-50 ps of window, estimate); in bypass (reset default) supply jitter is 33 ps peak | `analog/timing/pll_ring.spice:4`; `analog/wired_tx/sim_wiredtx.py:85` | BIND `pll_cdr.VDD`; `analog/pll_vreg/README.md:41` | `python3 scratch/reviews/mode-walk/wtx/phswing.py` | assembly + wired TX + timing |
| MW-32 | **Per-sampler slicer trim cannot be programmed**: 80 trim + 8 vsel pins vs 12 register bits; extracted systematic offset is -15 mV and the 60 mVppd point is "trimmed" | `analog/wired_rx/slicer.spice:11` | `rtl/pt_regmap_defs.svh:376` | `python3 cfg_map.py` | digital + wired RX |
| MW-33 | **Multiple drivers and undriven macro inputs.** `ct_word_clk` has three drivers, `island_on[0]` two (`wtx_fallback_control.WIRED_ON` vs the macro; `wired_on_ext` tied 0). `fault` has no source (no monitor block; floating high forces every TX off). `ref_clk`, `host_word_clk` are not in the isolation plan. `ring_osc` (165-255 MHz) goes straight into `fc_src[2]` (limit 156.25 MHz). `fc_src[5]`, `bias_ready`, `ref_present`, refbuf `READY`, lock bits undriven | `verification/chip_assembly/netlist.py:109,114,115,128` | `rtl/pt_digital_macro.sv:68,188`; `integration/pt_chip.sv:74`; `integration/macro-contract.md:153` | BIND | assembly + digital |
| MW-34 | **D2H launch location disagrees.** Floorplan reserves a south pad-edge gearbox (`rsv_d2h_gearbox`, an empty rectangle); RTL launches DDR inside the macro: 11 lanes at 3.2 ns UI cross >= 2.7 mm unbuffered. D2H reset drive/slew give 141 MHz at 5 pF, below full rate | `rtl/pt_host_link.sv:107-121,197` | `verification/chip_assembly/inventory.py:482-486`; IC:312 | read | digital + assembly |
| MW-35 | **No electrical idle, no bit repetition, no HS-pair signal detect.** `wire_idle` / `wiredtx.idle.idle` have no analog consumer (SATA OOB, PCIe idle required); WT19 repetition not in RTL (`rate_mode` dead); `pt_detect` sees only the USB pair or TX pads | `spec/interface-requirements.md:50,75` | `analog/wired_tx/wiredtx.spice:1124`; `analog/wired_rx/README.md:804-808` | `python3 cfg_map.py` | wired TX + digital |
| MW-36 | **Source ahead of published cells.** `pt_cdr` schematic r12 has `otr*` pins, layout r11 does not; `capture.py` is r7 (DW/EW/WSTB) while the published `wrx_cap` and the macro use DX/WCLK40 (consistent today, breaks on rebuild) | `analog/wired_rx/cdr.spice:22`; `analog/wired_rx/capture.py:530,570-574` | `analog/wired_rx/generated/cdr.lvs.spice:3`; `analog/wired_rx/generated/wrx_cap.lvs.spice:4707` | `python3 top_pins.py` (B) | wired RX |

### COSMETIC

- 80 bus fields / 397 bits with no consumer (`cfg_map.out` section 3): all `monitor.config.*`, `digital.guard_config.*`,
  `digital.hop_config.*`, most `clocktree.config.*`, `clockmux.config.*`, `cdr.config.*` timers, `*.config.enable`
  duplicates, `tmds.config.current_code`, `txpad.config.branch`, `usbdrive.*`, `consolidation.pll.owner/phase_tap`.
  63 legacy macro pins (`enable`, `mode8`, `*_trim`, `calibration_*`) have no analog consumer.
- Enable semantics differ: READMEs say `state != off`, RTL `en_eff` uses `== active`.
- Stale text: `integration/pt_wired_tx.sdc` and `integration/macro-contract.md:138,149` (10/20-bit boundary);
  `analog/rf_rx/README.md:131,153`; `analog/timing/prescale.spice:4`; `analog/wired_rx/ctle.spice:2`;
  `spec/analog-architecture.json` nets (older architecture); `integration/pt_chip.sv:1` (WIRE_RX = USB).
- `sim/tb_chip_io.sv:68` reads RESET_STATUS at 0x08 (now 0x0D), so the only chip-level digital bench fails.
- `rtl/pt_digital_macro.sv:84` still names `en_eff[11]` pll_host; `ESD_TEST`, `WCLK_OBS`, `WDBG_OBS` still chip ports.
- `spec/contract.json` `candidate_signal_sites` is stale against `bond_map_current` (already flagged there).

## 4. What agreed (both sides checked)

- Bias: all 20 connected consumers sink 10 uA into an NMOS diode; banks source it (`bias_sum.py`).
- ADC/DAC code format: two's complement, MSB-justified on both sides. Wired D-bus launch edges match the macro
  SDC and the block bench. Published capture and macro agree on DX/WCLK40; PH -> CKP -> D/E ordering consistent.
- Field widths and resets of rfdriver gain, LNA ctrim/att, rxmix offset, ptrim (8 x 5), hsbias, USB pull/trim.
- rxmix -> bbfilter CM; DAC CM into bbfilter/txmix; txmix -> txsum -> rfdriver is co-simulated by its owner.
- Chip top: positional port order of all three physical wrappers, pad cell OE/IE/PU/PD polarity, SPI mode 0,
  MISO tristate in reset, island EN/PG polarity and bit indices, 16-bit thermometer `bgap_trim`, biasgen/refchain
  field-to-pin bindings and defaults, ATB one-hot and group decode.

## 5. Could not trace

- Anything inside `pt_analog_physical` or any routed top: neither exists. All "assembly" verdicts are about
  `netlist.py` rules.
- Corners: every reviewer sim is one or a few corners (mixer/LO tt; CTLE chain and ptrim tt; CTLE CM tt/ss/ff;
  slicer CM schematic ss; phase swing schematic, five corners with an assumed source edge). The CKP load figures
  are estimates from extracted netlists, not AC measurements, and exclude block-to-block routing.
- Isolation/level cells at island crossings (ring phases pll -> wired, UP/DN wired -> pll, DX and ADC codes ->
  core): no instances exist to inspect. `ISO_conv/debug/pll/rf` dangle.
- Converter clock receiver tolerance to single-ended rail-to-rail CMOS; TX mixer gain/Psat/LO leakage with the
  real LO; `rx_direct` path; ADC input CM tolerance; one refbuf loaded by two ADCs.
- Pad internals (RF match with the new LNA, RF_TX clamp at 4.1 V peaks, USB HS eye, FS/LS timing, HS
  termination at corners, TX pad swing/CM/return loss vs protocol levels, T-coil, package channel).
- A closed CDR loop with the real capture phase detector; ring phase quality at the serializer pins; the
  `WORD_CLK40` round trip through iso clamp, macro clock tree and route; `wire_tx_clk` timing on current RTL.
- Host-link timing at the pads, SCLK edge after its ~2.9 mm route, transport framing against FPGA gateware
  (none in the tree), ATB force capability into each bias node.
- In-flight work by other agents (WT24 r7 pre-driver, `wtx_serq8`, `gen_regfile.py` edits of 20:49-20:51) was
  read as found in the working tree, which is ahead of committed evidence in places.

## 6. Boundary tables per mode

Verdict counts across the four parts: 85 OK, 158 MISMATCH, 24 UNVERIFIABLE. Every OK cites both sides.
Mode -> table: 2.4 GHz RX / TX / duplex = 6.1; wired RX low and top rate, USB, 100BASE-TX RX = 6.2; wired TX
CMOS / CML / TMDS / 100BASE-TX TX / WTX_EXT and the shared clock infrastructure = 6.3; host D2H / H2D, SPI-only
bring-up, ATB / debug observation = 6.4.

The tables cite part-local finding numbers. Map to section 3: radio F1=MW-1, F2=MW-2/19, F3=MW-3, F4=MW-4,
F5=MW-5, F6=MW-6, F7=MW-7, D1=MW-20, D2=MW-22, D3/D5=MW-21, D4=MW-29. Wired RX A1=MW-8, A2=MW-9, A3=MW-10,
A4=MW-11, A5=MW-14, A6=MW-18, A7=MW-25, D1/D3=MW-23, D2=MW-13, D4=MW-30, D5=MW-31, D6=MW-32, D7=MW-36,
D9=MW-12. Wired TX/clock F1=MW-2/16, F2=MW-15, F3=MW-12, F4/F8=MW-17, F5=MW-16, F6=MW-24, F7=MW-25, F9=MW-31,
F10=MW-33, F11=MW-2, F12=MW-15, F13/F14=MW-35. Digital F1=MW-26, F2=MW-27, F3/F4=MW-19, F5/F7/F8=MW-29,
F6/F14=MW-34, F9=MW-28, F10-F13=MW-33. Full findings text with reproduction paragraphs: the part files.

### 6.1 Radio (from part-rf.md)

#### 1. Boundary tables

##### 1.1 Shared by all three modes: LO, clocks, bias, references

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| regfile -> `pt_lo_ext` EXT / INT / CMLSEL | config source | `$P/analog/timing/lo_ext.spice:99` (ports; "EXT=INT=0 reset: mixer LO nodes clamped to VSS", :19-20) | `$P/analog/timing/README.md:94` ("RF LO mode (field needed)"); MAP `consolidation.quadrature.mode` and `quadrature.*` have bus = None; BIND `lo_ext.EXT/INT/CMLSEL` = UNBOUND | MISMATCH | No register bit, no decode. LO off in every mode. F1 |
| REF_IN / AUX_CLK pads -> `lo_ext.EXT_*` | pin, sharing | NL:84 (REF_IN -> EXT_I, AUX_CLK -> EXT_Q) | `$P/analog/timing/lo_ext.spice:5-7` (board I on REF_IN, Q on AUX_CLK) | OK | Consequence: in external-LO mode both clock-capable pads carry 2.4 GHz, see next rows |
| pads -> `lo_ext` | pad family used in the LO bench vs placed | `$P/analog/timing/lo_ext_pad.py:157` (refpad `tx_protected_pad` + VCM = VDD/2 on the I pair; Q pair on rf pair per IC:273 LO1) | INV:409 (v4: `pad_aux_clk` is `refpad` too) | MISMATCH | B3 window and the 93.8-95.1 deg Q-I (IC:551) were derived with unequal pads; stale for v4. F12 |
| refpad `VCM` pin | driver | NL:137 (`refpad.VCM -> REF_VCM`) | BIND net `REF_VCM` = {pad_ref.VCM, pad_aux_clk.VCM} only | MISMATCH | Assembly: no source for the pad VCM the LO bench sets to VDD/2 (`lo_ext_pad.py:157` `EVCM`). F6 |
| `lo_ext` LO_* -> rxmix `lo_p/n` | DC level | `$P/analog/timing/lo_ext.spice:129-130` (VB = 0.739 VDD on the LO node) | `$P/analog/rf_rx/rxmix_i.spice:641` (`pt_rfrx_vcm`, switch source at VDD/2) | OK | Both sides agree on source = VDD/2, gate DC = VB |
| `lo_ext` LO_* -> rxmix `lo_p/n` | swing / waveform | `$P/analog/timing/lo_ext_pad.py:258` (pass = peak Vgs >= 0.9 V, trough <= 0.5 V, sine); IC:549 (INT: VB +- ~0.45 V) | `$P/analog/rf_rx/tb.py:453-454`, `:867`, `:1076`, `:1226` (every rf_rx bench: 0/VDD square); `$P/analog/rf_rx/README.md:70` | MISMATCH | Simulated: -4.6 / -7.3 / -16.2 dB conversion vs the bench LO. D1 |
| `lo_ext` LO_* -> txmix `lo_p/n` | swing / waveform | same as above | `$P/analog/rf_tx/txmix_i.spice:4` ("DC-coupled rail-to-rail CMOS square"); `$P/analog/rf_tx/simulate.py:116-122` (0/3.3 V square, 50 ohm); only variant `run_benches.py:335` lo_high = 2.5 | UNVERIFIABLE | Gilbert quad probably still switches at +-0.3..0.45 V about 2.44 V but no bench shows gain/Psat/LO leakage with it. D1 |
| `lo_ext` LO node load | gate C assumed vs real | `$P/analog/timing/lo_ext_pad.py:13` (RX 12 x 5 um + TX 4 x 10 um + 22 fF) | `$P/analog/rf_rx/rxmix_i.spice:585-608` (12 x 5 um per LO phase); `$P/analog/rf_tx/txmix_i.spice:55-62` (4 x 10 um per phase) | OK | Route C (22 fF) is an assumption; v4 LO legs not extracted |
| QVCO -> `lo_ext.LOI_*` (internal LO) | instance exists | `$P/analog/timing/lcvco/qvco5.spice:12` (`pt_lc_qvco5`, IP/IN/QP/QN) | INV:36-91 MASTERS has no qvco / lo_mmd / lo_pfdcp / lo_lf / lo_obs; `$P/integration/core_bias.py:123-124` (`lc_vco_reserved` EN tied VSS) | MISMATCH | Internal LO is not on the chip. F7 |
| `pt_polyphase` -> `lo_ext.LOI_*` | level, input | `$P/analog/timing/polyphase.spice:9-10,14-15` (inverter limiters, CMOS levels; EN=0 drives LOI low) | `$P/analog/timing/lo_ext.spice:12-14` (LOI = tank sine ~1.2 Vpp about 1.7 V into CML gates); BIND `polyphase.INP/INN/EN` UNBOUND; IC:553 ("still fails extracted") | MISMATCH | The only thing on LOI in the assembly is a polyphase with no input; it would also short a QVCO tank if one were added. F7 |
| rfpll config -> `lo_mmd` N0..5, `lo_pfdcp` ICP0/1/PRE, QVCO BAND0..3 | config source | `$P/analog/timing/lo_mmd.spice:228`, `lo_pfdcp.spice:24`, `lcvco/qvco5.spice:12` | MAP `rfpll.config.*` all bus = None; no sigma-delta / band-search RTL in `$P/rtl` (grep mash/sigma/band_search: 0 files) | MISMATCH | F7 |
| REF_IN -> `ref_clk` | receiver instance | `$P/analog/timing/README.md:63,78` (refinput `diff_clk_rx` on REF_IN) | INV:309-310 (only `rx_aux_clk`, `rx_wclk_in`, `rx_wtx_ext`); BIND net `ref_clk` = {pll_cdr.REF, digital.ref_clk}, no driver | MISMATCH | Assembly: no REF_IN receiver. F2 |
| H2D_CLK -> clockmux PREF -> ring -> prescale -> HF -> CONV_CLK / HOST_CLK (host_follow) | whole path | `$P/analog/timing/clockmux.spice:14-16` (the only clock source in passive-LO RF mode) | NL:113 (`pll_cdr.REF -> ref_clk`, not PREF); BIND every clockmux/prescale pin UNBOUND, `pll_cdr.N4` UNBOUND; `$P/analog/timing/README.md:91-92` (PS_* and N4 "field needed") | MISMATCH | F2 |
| host_follow ring enable in RF mode | enable vs regfile rule | NL:37 + BIND `pll_cdr.EN = EN_EFF_pll_cdr` = `cdr.state == active` (`$P/rtl/pt_digital_macro.sv:177`) | `$P/rtl/pt_regfile.sv:1178,1271` (rule 15: any ADC/DAC/LNA/rfdriver active => commit rejected unless `cdr.state != active`); INV:275-277 (pll_host deleted) | MISMATCH | The one remaining ring that can do host_follow cannot be enabled while RF is active. F2 |
| CONV_CLK -> ADC/DAC `CLKP/CLKN` | level | `$P/analog/timing/clockmux.spice:3` (single-ended CMOS) | `$P/analog/converters/benches.py:193-197` (differential 1.45/1.85 V about 1.65 V) | MISMATCH | No cell converts; BIND `adc_*.CLKP/N`, `dac_*.CLKP/N` UNBOUND. F3 |
| CONV_CLK -> ADC | duty / high time | `$P/analog/timing/clockmux.spice:17,30` (AND-OR mux of a ring/prescaler clock, ~50 %) | `$P/analog/converters/benches.py:524-525` (40 MHz/6 ns high with ILEN=1; 20 MHz/10 ns with ILEN=0); `benches.py:647` ("acquisition_ns is realised by the ADC_CLOCK duty cycle, not inside this block") | MISMATCH | Nobody makes the pulse. F3 |
| analog -> digital `rf_rx_clk`, `rf_tx_clk` | source | `$P/integration/pt_chip.sv:126` (outputs of the blackbox) | no cell or NL rule drives them (BIND: digital datapath dangling) | MISMATCH | F3 |
| core_bias -> every `ibias` | direction, magnitude | `$P/analog/core_support/distribution/circuits_dist.py:3-4,66-76` (PMOS bank sources 10 uA from the island rail) | `$P/analog/rf_rx/bbfilter_i.spice:63-65` (NMOS diode), `$P/analog/rf_tx/txmix_i.spice:63`, `$P/analog/converters/benches.py:68,217` (10 uA into the pin) | OK | All RF/converter consumers sink 10 uA into an NMOS diode |
| core_bias bank EN -> bbfilter_i/q | enable | `$P/integration/core_bias.py:126-127` (bank output gated by EN_<consumer>) | BIND `EN_EFF_bbfilter_i` = {core_bias.EN_bbfilter_i} only, no driver; `$P/rtl/pt_digital_macro.sv:73-92` (en_eff has no bbfilter bit) | MISMATCH | F4 |
| core_bias VREF0 -> `refbuf.VREF0` | net | `$P/integration/core_bias.py:82,133,143-144` (VREF0 = 5/6 VBG; "parent binds VREF0 to refbuf.VREF0") | NL:53,64 (refbuf.VREF0 on `VREF0_CONV`); BIND `core_bias.VREF0 -> ATBN_master_vref0` (dangling), `VREF0_CONV` = {refbuf.VREF0, atb1_leaf2.NODE} | MISMATCH | Assembly net-name mismatch: refbuf reference floats. F6 |
| core_bias VCM -> `adc_*.VCM` | net | `$P/integration/core_bias.py:82,144` | NL:65; BIND `VCM_CONV` = {adc_i.VCM, adc_q.VCM, atb1_leaf37.NODE}, `core_bias.VCM -> ATBN_master_vcm` | MISMATCH | VCM is used in normal conversion (`$P/analog/converters/rtl/adc_sar_logic.v:32,92` lsb_rst to VCM every track phase), not only in test. F6 |
| refbuf -> ADC `VREF` | level | `$P/analog/converters/benches.py:693-696` (FFT bench with extracted refbuf, VREF0 = 1.0 V ideal) | NL:64 (`VREF_CONV` shared by both ADCs) | OK | One refbuf for two interleaved ADCs was not benched (FFT is one ADC) |

##### 1.2 RX narrowband (RF_RX pad -> D2H)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| RF_RX pad -> `pt_lna.rf_in` | pin, pad model in bench | NL:57; INV:406 (`rf_pair`) | `$P/analog/rf_rx/tb.py:82` (`with_pad_rf_pair`) | OK | |
| LNA `src_p/src_n` -> ground pads | pin exists | `$P/analog/rf_rx/lna.spice:8,41` (CS sources on `src_p`) | `$P/spec/contract.json:77` (mention only); INV pad list has no such pads; BIND `lna.src_p/n` UNBOUND | MISMATCH | LNA has no source return in the assembly. F5 |
| LNA `tank_p/tank_n` -> spirals | load exists | `$P/analog/rf_rx/README.md:50-51` (two spirals, "DRC-only cells placed at assembly; benches insert the model") | INV MASTERS: no spiral; BIND `lna.tank_p/n` UNBOUND | MISMATCH | LNA has no load in the assembly. F5 |
| LNA `rf_out` / `rf_outq` -> rxmix_i / rxmix_q | pin mapping | `$P/analog/rf_rx/tb.py:889,893-894` (rf_out -> I mixer, rf_outq -> Q mixer); `lna.spice:253,255` (separate 16 um MIMs) | NL:57-58 (both mixers on `RFA_*` = rf_out; `rf_outq` UNBOUND) | MISMATCH | Assembly follows the stale `README.md:131`. F5 |
| LNA out -> rxmix RF | DC | `$P/analog/rf_rx/lna.spice:253` (AC-coupled) | `$P/analog/rf_rx/rxmix_i.spice:585` (switch to TIA virtual ground) | OK | |
| regfile -> LNA `lobias` | config | `$P/analog/rf_rx/lna.spice:24` | MAP: no `lna.bias.lo` (IC:1222 asks for it) | MISMATCH | F5 |
| regfile -> LNA `ct0..3` | width / reset | DEFS:470-471 (4 bits; MAP default 7) | `$P/analog/rf_rx/tb.py:121` (`LNA_CT_RESET = 7`) | OK | Meaning changed twice (match trim -> inert -> tank tune); the per-process code is a bring-up item |
| regfile -> LNA `att0..4`, `gain_lo` | width | DEFS:476-477 (5 bits), DEFS:324-325 | `$P/analog/rf_rx/lna.spice:8` | OK | Fast-gain mapping (`$P/rtl/pt_digital_macro.sv:98-108`) cites RC-16g levels; RC-16j moved the attenuator across the tank, levels not re-derived: UNVERIFIABLE |
| regfile -> LNA / rxmix `en` | semantics | `$P/analog/rf_rx/README.md:142,145` (`state != off`) | `$P/rtl/pt_digital_macro.sv:169-170,184` (`state == active`) | MISMATCH | "warm" keeps the block off in the RTL. C2 |
| regfile -> rxmix `ofs0..4, ofs_sign` | width | DEFS:128-131 (6 bits each) | `$P/analog/rf_rx/rxmix_i.spice:637` | OK | Encoding (bit 5 = sign) is by README proposal only (`README.md:146`) |
| regfile -> rxmix `hib` | config | `$P/analog/rf_rx/netlists.py:164-165` (1 = RX, 0 = duplex; "validator ties it to NOT lna.bias.lo") | MAP: no field; BIND `rxmix_*.hib` UNBOUND | MISMATCH | F5 |
| rxmix `bb` -> bbfilter `rx_in` | CM | `$P/analog/rf_rx/rxmix_i.spice:641,651` (TIA + input at local VDD/2) | `$P/analog/rf_rx/README.md:77-78` (CMFB to the midpoint of the core inputs); `tb.py:517` (bench CM 1.65 V) | OK | |
| regfile -> bbfilter `en`, `dir_tx` | decode | `$P/analog/rf_rx/README.md:147` (`direction != isolated` / `== tx`) | DEFS:82-83 (raw 2-bit field); no decode in `$P/rtl/pt_digital_macro.sv:161-186`; NL:30 points at dropped `rxfilter_i.state.state` | MISMATCH | F4 |
| regfile -> bbfilter `gain0..5, gainc0..1` | width / encoding / reset | IC:153-160 (k[5:0] + 2 coarse bits via a 17-entry LUT "in the digital"; all-zero = muted; 0 dB needs gain2 = 1) | DEFS:90-91 (4 bits, MAP default 0, "linear (code+1), 0..24 dB"); `$P/rtl/pt_digital_macro.sv:109-115` (fast gain uses 20 log10(1+c)) | MISMATCH | No LUT exists. Wired directly: reset = muted, max +11.5 dB. F4 |
| regfile -> bbfilter `bw0..3`, `fc_fine0..2` | width / reset | `$P/analog/rf_rx/README.md:150` (7-bit cap code, reset 8) | DEFS:88-89 (4 bits, MAP default 0); no fc_fine field | MISMATCH | F4 |
| regfile -> bbfilter `qt0..3` | width / reset | `$P/analog/rf_rx/README.md:151` (4 bits, reset 6; README:98 "cap code <= 1 requires qt >= 6") | DEFS:92-93 (2 bits, default 1) | MISMATCH | Reset state (cap 0, qt 1) is outside the cell's own stability rule. F4 |
| regfile -> bbfilter `dcf0..7, dcf_sign`, `rx_direct`, `byp_s1/s23`, `obs_sel`, `inj` | source | `$P/analog/rf_rx/bbfilter_i.spice:796` | DEFS:86-87 (`rx_direct`), DEFS:46-49 (bypasses), DEFS:40-41 (bb_tap mode, needs decode); no DCOC field in MAP | MISMATCH | Fields exist for rx_direct/bypass but nothing binds or decodes them; fine DCOC has no bits. F4 |
| bbfilter `out_rx` -> ADC `INP/INN` | CM | `$P/analog/rf_rx/tb.py:517` (out CM = in CM = VDD_rf/2) | `$P/analog/converters/benches.py:231` (1.65 V ideal) | OK | ADC not benched at 1.575 / 1.675 V input CM (rail 3.15 / 3.35 V) |
| bbfilter `out_rx` -> ADC | drive / source impedance | `$P/analog/rf_rx/bbfilter_i.spice:772` (NMOS-only 30/0.28 series switch) | `$P/analog/converters/benches.py:231` (zero-ohm source) | UNVERIFIABLE | IC:565 RC-7 measured 0.70 LSB8 at 0.71 V diff into a switched-load model; not at ADC full scale (+-0.87 V), not with the bb_tap gate that NL:79 hangs on the node |
| bbfilter `obs/inj` <-> bb_tap | pin mapping | `$P/analog/rf_rx/README.md:137` (bb_tap.in <- bbfilter.obs, bb_tap.inj -> bbfilter.inj) | NL:79-80 (bb_tap.in on the ADC input net, bb_tap.inj on the DAC output net; bbfilter obs/inj UNBOUND) | MISMATCH | D4 |
| regfile -> ADC `ILEN` | config | IC:182 (`adc_*.config.interleave` needed) | MAP: no such field; BIND `adc_*.ILEN` UNBOUND | MISMATCH | F3 |
| ADC `CODE/CODEB/DONE/DONEB` -> `rf_rx_sample`, `rf_rx_valid` | glue | IC:184 ("the RF RX stream must take A and B alternately") | `$P/rtl/pt_core.sv:71-72` (one 24-bit sample per rf_rx_clk edge, valid used unsynchronised); no RTL references CODEB/DONEB | MISMATCH | No A/B merge, no valid generator. F3 |
| ADC code format -> digital | encoding | `$P/analog/converters/rtl/adc_code_reg.v:22` (10-bit two's complement) | `$P/rtl/pt_core.sv:72` (mode8 takes [23:16],[11:4], i.e. MSB-justified 12-bit fields) | OK | Requires `{CODE, 2'b00}` wiring per `adc_sar_logic.v:20-21`; that wiring is not in NL |
| ADC outputs (conv island) -> digital macro (core) | isolation | NL:252 (`ISO_conv` from the island switch) | BIND dangling list contains `ISO_conv`, `ISO_rf`, `ISO_pll` | UNVERIFIABLE | No iso_clamp binding for CODE/DONE; datapath not bound at all |

##### 1.3 TX (H2D -> RF_TX pad)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| `rf_tx_sample` -> DAC `CODE0..9` | encoding | `$P/rtl/pt_interp2x.sv:9-10,34` ([11:2] I, [23:14] Q, two's complement) | `$P/analog/converters/rtl/dac_logic.v:24` (two's complement -> offset binary) | OK | Wiring itself is not in NL (BIND `dac_*.CODE*` UNBOUND) |
| `rf_tx_clk_out` -> DAC `CLKP/CLKN` | pin exists, edge | `$P/rtl/pt_digital_macro.sv:43`; IC:1011 DT-6 (DAC must capture on the falling edge) | `$P/integration/pt_chip.sv:64-85` (macro instance has no `.rf_tx_clk_out`; blackbox has no such port); `dac_logic.v:22` (captures on rising CK = CLKP > CLKN) | MISMATCH | Forwarded clock is not connected at chip top; polarity (swap P/N) and CMOS -> low-swing conversion undefined. F3 |
| `rf_tx_request` | source | `$P/rtl/pt_digital.sv:99-104` (sample transfers on request && valid) | DAC has no request output (`$P/analog/converters/dac_i.spice:1196`) | MISMATCH | Must be a tie-high in the (missing) analog top. F3 |
| `rf_mute` + `rfdriver.mute.mute` -> `rfdriver.mute` | glue | `$P/rtl/pt_core.sv:261`; DEFS:360-361 (register, default 1) | `$P/analog/rf_tx/rfdriver.spice:6` (one `mute` pin); BIND `rfdriver.mute` UNBOUND | MISMATCH | OR of the two is nowhere. D5 |
| regfile -> DAC `HOLD_ZERO`, `EN` | config | DEFS:274-277 (hold_zero default 1) | `$P/analog/converters/rtl/dac_logic.v:24` | OK | `dac_*.config.enable` has no consumer (en_eff uses state only, `pt_digital_macro.sv:164-165`). C2 |
| DAC `OUT` -> bbfilter `tx_in` / txmix `dac` | CM | IC:191 (CM loop to VDD/2; extracted 1.62-1.77 V per `$P/analog/converters/README.md:175`) | `$P/analog/rf_tx/simulate.py:223` (cm = 1.65); `$P/analog/rf_rx/tb.py:1018-1019` (1.65) | OK | Conv rail vs RF rail differ by up to 0.2 V in the window -> up to 0.1 V CM offset; filter CMFB follows its input |
| DAC `OUT` -> bbfilter `tx_in` | swing through the switch | `$P/analog/converters/README.md:174` (+-0.98 V diff, i.e. legs to ~2.23 V) | `$P/analog/rf_rx/bbfilter_i.spice:769` (NMOS-only 30/0.28 switch); `tb.py:1006` (bench amp 0.2 V diff) | UNVERIFIABLE | Switch Ron at 2.2 V is ~350 ohm (my DC point, tt) vs 111 ohm at 1.65 V, in series with the PGA input R. Never benched at DAC full scale. D3 |
| DAC `OUT` load | load in DAC bench vs real | `$P/analog/converters/benches.py:324` (100 fF per leg, no resistive load) | NL:68-71,80 (bbfilter tx_in + txmix dac + bb_tap inj + route on the same net); stage-1 input is k/(4R) conductance (IC:153) | MISMATCH | DAC's 1 kohm/leg load is shunted by the PGA input (~8 kohm at 0 dB, lower at higher k). Gain error only. D3 |
| bbfilter `out_tx` -> txmix `bb` | CM, pin | `$P/analog/rf_rx/bbfilter_i.spice:773` (TG to out_tx; CM follows input) | `$P/analog/rf_tx/txmix_i.spice:22` (NMOS pass switch into the gm gate); `simulate.py:223` | OK | |
| regfile -> txmix `sel_dac`, `sat` | config | DEFS:84-85 (`tx_dac_direct`), DEFS:108-109 (`sat_mode`) | `$P/analog/rf_tx/txmix_i.spice:5` | OK | Fields exist; NL has no rule (BIND UNBOUND) |
| txmix -> txsum -> rfdriver | CM, load | `$P/analog/rf_tx/simulate.py:232-268` (the three blocks co-simulated, open-drain into txsum loads) | NL:72-76 (same topology) | OK | Only block boundary pair in scope that was verified together |
| regfile -> rfdriver `g0..3` | width / reset | DEFS:356-357 (4 bits; MAP keeps code[7:4], default 192 -> g = 12) | `$P/analog/rf_tx/rfdriver.spice:3` (g3..g0 = code[7:4]) | OK | |
| rfdriver `pad` -> RF_TX pad | DC feed, clamp | `$P/analog/rf_tx/simulate.py:139-159` (pads fed from the RF rail through chokes, 2 ohm + 1 pF + optional extracted pad) | `$P/analog/pads/README.md:167-180` (RF_TX rests at 3.3 V, peaks ~4.1 V, gate-coupled shunt); INV:412 (`rf_pair`) | OK | Not re-derived by me; pads reviewer owns the clamp numbers |

##### 1.4 Duplex (GX-3)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| shared LO -> rxmix + txmix | load with both on | `$P/analog/timing/lo_ext_pad.py:13` (both gate sets always present) | NL:59,73 (same LO nets to both mixers) | OK | Same LO frequency for TX and RX by construction (no offset duplex) |
| mode (a) `direction = rx` + `tx_dac_direct` | filter path | IC:820 GX-3(a) | `$P/analog/rf_tx/txmix_i.spice:23` (`dac_p` direct input); `$P/rtl/pt_regfile.sv:1166` (rule 3 allows it) | OK | Depends on F4 (bbfilter decode) and F1-F3 like everything else |
| mode (b) `direction = tx` + `rx_direct` | ADC drive | `$P/analog/rf_rx/bbfilter_i.spice:774` (rx_in -> out_rx through an NMOS-only switch, no filter, no PGA) | `$P/analog/converters/benches.py:231` (ideal source) | UNVERIFIABLE | The rxmix TIA (400 uA output stage, `README.md:65`) drives the ADC sampling cap directly; no bench |
| LNA `lobias`, rxmix `hib` in duplex | config | IC:1222 (validator forces `lna.bias.lo = 1` when TX is on; power budget relies on it) | MAP has neither field | MISMATCH | 240 mA duplex ceiling not enforceable. F5 |
| ADC clock and DAC clock together | rates | `$P/rtl/pt_digital.sv:89-91` (halfband: rf_tx_clk = 80 MHz, core at /2) | `$P/analog/timing/clockmux.spice:10-11,30` (one CONV_CLK output) | MISMATCH | 80 MS/s DAC with 40 MS/s ADC needs two related clocks; one mux output, no divider. D2 |
| TX -> RX isolation | analysis | IC:826 GX-9 (analysis requested) | no result file found under `$P/analog` or `scratch/reviews` | UNVERIFIABLE | |

---

### 6.2 Wired receive, USB, 100BASE-TX RX (from part-wrx.md)

#### Boundary tables

Verdict OK needs both sides cited. MISMATCH = the two sides disagree or one side does not exist. UNVERIFIABLE = no artefact to compare.

##### Mode 1 and 2: wired RX through the HS pair (480 Mb/s - 1.25 Gb/s, and 2.5 - 3.24 Gb/s quarter rate)

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

##### Mode 3: USB (pad_usb pair)

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

##### Mode 4: 100BASE-TX receive (IX-9 .. IX-13)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| pt_vthdac -> pt_slicer VTAP/VTAN/VTBP/VTBN | pins, levels | `vthdac.spice:5,8` CM ~0.8 V, +/-1.6 V diff FS | `slicer.spice:11`; slicer bench default 0.8 V `sims.py:299` | OK (cells) | `vthdac` not in inventory/netlist; `BIND` slicer.VT* `UNBOUND`. |
| vthdac A[7:0], B[7:0], vth_en; slicer vsel_e*[1:0] | fields | `vthdac.spice:8`; `slicer.spice:11` | none in `pt_regmap_defs.svh` (`IC:982` asked for `cdr.vth_a/b[7:0]`, `cdr.vth_sel_e0..e3`, `cdr.vth_en`) | **MISMATCH** | Reset state safe (aux pairs off). |
| fast threshold update (IX-11) | H2D opcode | `IC:783` | only opcode 4 (RF fast gain) exists: `rtl/pt_core.sv:270-279`, `rtl/pt_quad_link.sv:165` | **MISMATCH** | No baseline-wander loop; the HS pad's on-die AC coupling has a 0.67-1.07 MHz high-pass (`IC:800`). |
| raw dual-lane capture (IX-12) | edge word to the host | capture exports EW only as cell pins; published cell gears DW only into DX (`README.md:377`) | macro "has no edge-sample input today (DX = data only)" `IC:1055`; no `psel_force` / `cfg_raw` field | **MISMATCH** | The FPGA cannot get the second (threshold) lane. |
| CTLE LF zero (IX-13) | field | `ctle.spice:8-12` lf_zero[2:0], effective at peak code 7 | no lf_zero field; peak code limited to 0..3 (`pt_regmap_defs.svh:268`, 2 bits) | **MISMATCH** | |
| rate | ring / mode | 125 MBd, ring 750 MHz = 6x, full-rate mode (`IC:784`) | needs B1 = 1 (full) and a fixed odd psel: no source (A3) | **MISMATCH** | |
| RX needs from TX (other reviewer) | MLT-3 levels | `IC:781` POST polarity bit `wiredtx.config.post_polarity` | pt_wiredtx has pin POST_POL (`wiredtx.spice:1124`); no such field in `pt_regmap_defs.svh` | **MISMATCH** | Needed for an MLT-3 loopback/peer test of the RX path. |

### 6.3 Wired transmit and clock infrastructure (from part-wtx-clk.md)

#### 1. Wired TX, retimed CMOS path (<= 2.5 Gb/s)

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

#### 2. Wired TX, CML path (2.7-3.24 Gb/s)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| serializer final stage | CML 2:1 present | `scratch/reviews/MANDATE.md` (final 2:1 is CML); `analog/wired_tx/cml_ser.py:1-8` (wtx_cml2) | `analog/wired_tx/wiredtx.spice:974-1010` (`wtx_serq4c`: CMOS window mux `wtx_omuxt`, no cmlt cell) | MISMATCH | the CML stage is not in the published block |
| rate plan | 2.7-3.24 Gb/s | IC:224 (WT21: core never above 2.5 Gb/s), IC:226 (WT23: quantified, NOT built) | `integration/pt_digital_macro.sdc:21-22` (wtx constrained at 12.3 ns = 3.24 Gb/s) | MISMATCH | digital is constrained for a rate no analog block provides |
| serq8 (in flight) | phases | `analog/wired_tx/serq8_macro.py:45-46` (8 phases PH0..PH315, modes M2/R4/R8) | `wiredtx.spice:1124` (4 phase pins, MODE_H/MODE_F) | MISMATCH | top-level pin list must change; assembly and regmap have no rows for it |
| serq8 (in flight) | ring range | `serq8_macro.py:5-6` (n=1: ring 300-405 MHz for 2.4-3.24 Gb/s) | `netlist.py:121` BAND=VDD; IC:974 (high band bottom 484 MHz at ff) | MISMATCH | every x1 rate of serq8 needs BAND=0, which has no register bit |
| serq8 (in flight) | 40-bit load vs split launch | `serq8_macro.py:3-4` (8 streams x 5 bits, whole word loaded at once) | `rtl/pt_core.sv:238-241` (halves launched half a period apart) | UNVERIFIABLE | common valid window is [rise + 3.5 ns, rise + T/2]: 2.7 ns at T = 12.35 ns |
| pre-driver -> pad | CML pre-driver | IC:1156-1193 (cell `wt24_tr7` in scratch; review NO-GO) | pad switch still 8 x 20/0.28 (`physical.spice`), IC:1148 asks for 0.6x resize | MISMATCH | neither the cell nor the resized pad is published; `wtx.predrv_trim[1:0]` and `EN_POST = (post != 0)` have no register or decode |
| CML bench | resembles neighbour | `analog/wired_tx/sim_cml.py:1-8` (ideal streams, tcq swept, schematic) | none | UNVERIFIABLE | never run from the extracted core or into the pad |

#### 3. TMDS, 100BASE-TX (IX-9), WTX_EXT fallback

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

#### 4. Clock infrastructure, per consumer

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

### 6.4 Host link, SPI-only bring-up, ATB / debug (from part-dig.md)

#### 1. Host D2H (chip -> FPGA)

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

#### 2. Host H2D (FPGA -> chip)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| H2D pads -> macro | cell, IE, thresholds, pulls | `pt_provider_io.sv:22-24,48-52` (bi_24t OE=0 IE=1 CS=0 PU=PD=0) | `gf180mcu_fd_io.v:64` (`and (Y,PAD,IE)`), `pt_chip.sv:94` | OK | inputs float while the FPGA is unconfigured (also in `m6-powerup/audit/iso_audit.json` pads) |
| H2D capture clock | which clock captures | `rtl/pt_host_link.sv:140` (h2d_clk -> pt_h2d_gearbox) | `pt_chip.sv:60-61` | OK | |
| H2D needs host_word_clk | reset release | `rtl/pt_digital_macro.sv:138,155` (`host_rst_n = rst_n & rate_hold_n`), `rtl/pt_host_link.sv:480` (hold_n reset 0, released by `clk`) | `clockmux.spice:31` | OK (as designed) | H2D cannot be exercised with H2D_CLK alone; same single point as D2H |
| H2D pad speed | bi_24t input f_max | `evidence/digital-hardening-evidence.json` hostio: `!CS&IE&!OE` 235 MHz tt, 191.6 MHz ss_125C_2v97 | target 156.25 MHz | OK | CS=0 is required (CS=1: 148 MHz at ss) and is what the binding ties |
| H2D pads -> macro distance | placement | `inventory.py:396` (macro top at y 4670), `pin_order.cfg:12` (h2d on N) | `spec/contract.json` candidate_signal_sites H2D bidir[26..36] | OK | pads abut the macro north edge; `rsv_h2d_gearbox` is likewise an empty reserve but nothing is needed there (`IC:580`) |
| macro timing | h2d / hcore closure | `scratch/digital-timing-close/NOTES.md` (TC2A: h2d -3.57, hcore -5.63, hddr -1.91 ns at ss_032C) | `integration/pt_digital_macro.sdc:71,78,126,137` | UNVERIFIABLE | not closed; committed evidence file is two architectures old (F2) |
| fallback when the link is down | capture/playback over SPI | `rtl/pt_digital.sv:119-129` (MEMORY v3, core reset from `rst_n`, SCLK port) | - | UNVERIFIABLE | exists in RTL; still needs wire/rf clocks from analog, so not an SPI-only function |

#### 3. SPI-only bring-up

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

#### 4. ATB / debug observation

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
