# Mode walk, part RF: 2.4 GHz RX, TX, duplex (2026-11-13)

Scope: REF_IN/AUX_CLK pads -> LO -> mixers; RF_RX pad -> LNA -> rxmix -> bbfilter -> ADC -> digital;
digital -> DAC -> bbfilter/txmix -> txsum -> rfdriver -> RF_TX pad; converter clocks; bias/reference; enables/config.

Abbreviations: `$P` = `projects/programmable_transceiver_platform`; `IC` = `scratch/reviews/interface-changes.md`;
`NL` = `$P/verification/chip_assembly/netlist.py`; `INV` = `$P/verification/chip_assembly/inventory.py`;
`BIND` = `scratch/integration/m6-powerup/chipnet/binding.json` (today's run of NL);
`DEFS` = `$P/rtl/pt_regmap_defs.svh`; `MAP` = `$P/spec/register-map.json` (cited by field name).

How to read the verdicts. There is no `pt_analog_physical` (`$P/integration/pt_chip.sv:119` is a blackbox), so a
"chip" exists only as NL's binding rules. Where a mismatch is in NL (a wrong or missing binding rule) I say "assembly";
where no block/RTL provides the function at all I say "nobody". "Inferred" = from numbers in the artefacts, not simulated by me.
One simulation was run (finding D1); everything else is read from the cited artefacts.

---

## 1. Boundary tables

### 1.1 Shared by all three modes: LO, clocks, bias, references

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

### 1.2 RX narrowband (RF_RX pad -> D2H)

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

### 1.3 TX (H2D -> RF_TX pad)

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

### 1.4 Duplex (GX-3)

| boundary | aspect | side A (file:line) | side B (file:line) | verdict | note |
|---|---|---|---|---|---|
| shared LO -> rxmix + txmix | load with both on | `$P/analog/timing/lo_ext_pad.py:13` (both gate sets always present) | NL:59,73 (same LO nets to both mixers) | OK | Same LO frequency for TX and RX by construction (no offset duplex) |
| mode (a) `direction = rx` + `tx_dac_direct` | filter path | IC:820 GX-3(a) | `$P/analog/rf_tx/txmix_i.spice:23` (`dac_p` direct input); `$P/rtl/pt_regfile.sv:1166` (rule 3 allows it) | OK | Depends on F4 (bbfilter decode) and F1-F3 like everything else |
| mode (b) `direction = tx` + `rx_direct` | ADC drive | `$P/analog/rf_rx/bbfilter_i.spice:774` (rx_in -> out_rx through an NMOS-only switch, no filter, no PGA) | `$P/analog/converters/benches.py:231` (ideal source) | UNVERIFIABLE | The rxmix TIA (400 uA output stage, `README.md:65`) drives the ADC sampling cap directly; no bench |
| LNA `lobias`, rxmix `hib` in duplex | config | IC:1222 (validator forces `lna.bias.lo = 1` when TX is on; power budget relies on it) | MAP has neither field | MISMATCH | 240 mA duplex ceiling not enforceable. F5 |
| ADC clock and DAC clock together | rates | `$P/rtl/pt_digital.sv:89-91` (halfband: rf_tx_clk = 80 MHz, core at /2) | `$P/analog/timing/clockmux.spice:10-11,30` (one CONV_CLK output) | MISMATCH | 80 MS/s DAC with 40 MS/s ADC needs two related clocks; one mux output, no divider. D2 |
| TX -> RX isolation | analysis | IC:826 GX-9 (analysis requested) | no result file found under `$P/analog` or `scratch/reviews` | UNVERIFIABLE | |

---

## 2. Findings, ranked

### DEAD MODE

**F1. No way to turn the LO on (RX, TX, duplex).** `pt_lo_ext` needs EXT=1 (passive external), INT=1 (internal) or
EXT=INT=CMLSEL=1 (external through the CML limiter); with all three low the mixer LO nodes are clamped to VSS
(`$P/analog/timing/lo_ext.spice:19-20,97-99`). No register field drives them: `consolidation.quadrature.mode` and all
`quadrature.*` fields have `bus: null` in MAP, `$P/analog/timing/README.md:94` still says "RF LO mode (field needed)", CMLSEL
(added by LO11) is not even in that table, and BIND lists `lo_ext.EXT/INT/CMLSEL` as UNBOUND. Reproduce:
`python3 -c "import json;b=json.load(open('scratch/integration/m6-powerup/chipnet/binding.json'));print({p:v['net'] for p,v in b['bindings']['lo_ext'].items() if p in('EXT','INT','CMLSEL')})"`.
Owner: digital (2-3 bits + EXT/INT exclusion rule), timing (decode table), assembly (binding).

**F2. No sample clock and no host clock in the external-LO RF mode (RX, TX, duplex).** With the baseline LO, REF_IN and
AUX_CLK both carry 2.4 GHz, so the only reference is H2D_CLK through host_follow
(`$P/analog/timing/clockmux.spice:14-16`). That path is broken in four places: (1) the clockmux PREF select
(PS_REF/PS_AUX/PS_H2D) and the ring modulus N4 have no register field (`$P/analog/timing/README.md:91-92`); (2) NL:113
binds `pll_cdr.REF` to `ref_clk`, not to `clockmux.PREF`, and every clockmux/prescale pin is UNBOUND; (3) pll_host
was deleted (INV:275-277) and the surviving ring's enable is `cdr.state == active`
(`$P/rtl/pt_digital_macro.sv:177`), which the register file itself rejects whenever an ADC, DAC, LNA or rfdriver is
active (`$P/rtl/pt_regfile.sv:1178`, commit code 0x10 at :1271); `en_eff[11]` (rfpll.state, :178) still exists but
drives nothing; (4) there is no `diff_clk_rx` on REF_IN at all (INV:309-310), so `ref_clk` has sinks and no driver even
for a mode where REF_IN is a reference. Owner: digital (ring-enable ownership in RF mode, PREF/N4 fields), timing +
assembly (PREF -> ring REF, REF_IN receiver, clockmux bindings).

**F3. Converter clock and data glue does not exist (RX, TX, duplex).** (a) ADC/DAC `CLKP/CLKN` were verified only with a
0.4 V differential clock about 1.65 V (`$P/analog/converters/benches.py:193-197`); the source is a single-ended CMOS mux
output (`clockmux.spice:3`). (b) The ADC acquisition time is the clock high time: 6 ns at 40 MHz (ILEN=1) or 10 ns at
20 MHz (ILEN=0) (`benches.py:524-525,647`), and `adc_*.config.acquisition_ns` is dropped from the bus; nothing shapes
the pulse. Inferred, not simulated: with a 50 % clock the single core has 25 ns to convert at 20 MS/s against a
measured tt conversion of ~30-35 ns (`converters/README.md:167` 34.8 ns v2; IC:753 t_done <= 29.96 ns v3), so it fails at tt; interleaved at 40 MS/s each core has
37.5 ns against 39.1 ns worst corner (IC:952). A 50 % clock works only up to roughly 11 MS/s. (c) `ILEN` has no
register (IC:182 asked for `adc_*.config.interleave`), and no RTL takes `CODEB/DONEB`, so 40 MS/s is unreachable and
`rf_rx_valid` has no generator (`$P/rtl/pt_core.sv:71-72` uses it unsynchronised in the rf_rx_clk domain). (d) `rf_rx_clk`
/ `rf_tx_clk` are outputs of a blackbox (`pt_chip.sv:126`). (e) DT-6's `rf_tx_clk_out` (`pt_digital_macro.sv:43`) is not
connected in `pt_chip.sv:64-85`, and the DAC captures on the rising edge of CLKP-CLKN (`dac_logic.v:22`) while DT-6
requires the falling edge of the forwarded clock: a P/N swap someone must own. (f) `rf_tx_request` has no source.
Owner: timing (a converter clock cell: CMOS -> differential, pulse shaper, /2 for the halfband case), digital (ILEN
field, A/B merge, valid), converters (confirm single-ended CMOS tolerance of `clkrx`), integration (pt_chip ports).

**F4. bbfilter has no enable, and its gain/bandwidth/Q codes do not match the register map (RX; TX through the filter;
duplex).** `en` and `dir_tx` are meant to be decoded from `consolidation.bbfilter.direction`
(`$P/analog/rf_rx/README.md:147`), but the digital exports the raw 2-bit field and has no bbfilter entry in `en_eff`
(`$P/rtl/pt_digital_macro.sv:73-92`, assigns :161-186); NL:30 keys the enable on `rxfilter_i.state.state`, which is dropped from the bus,
so `EN_EFF_bbfilter_*` has no driver and the bias bank never sources BIAS_bbfilter (`$P/integration/core_bias.py:126-127`).
Gain: the cell takes k[5:0] plus two +12 dB bits through a 17-entry LUT "in the digital", all-zero = muted, 0 dB =
gain2 (IC:153-160, `tb.py:114`); the map has a 4-bit linear code with reset 0, and the fast-gain table in
`pt_digital_macro.sv:109-115` assumes 20 log10(1+c). No LUT exists. Wired bit-for-bit the reset state is muted and the
maximum is +11.5 dB instead of +42 dB. Bandwidth: 7-bit cap code, reset 8, vs a 4-bit field with reset 0. Q: 4-bit
`qt`, reset 6, vs a 2-bit field with reset 1; the reset combination (cap 0, qt 1) violates the cell's own rule "cap code
<= 1 requires qt >= 6" (`README.md:98`). `dcf[7:0]/dcf_sign`, `fc_fine`, `obs_sel`, `inj` have no bits. Owner: digital
(fields + decode/LUT), rf_rx (publish the LUT and safe reset as data), assembly.

**F5. Today's LNA is not integrated (RX, duplex).** The RC-16i/j/k LNA needs `src_p/src_n` on two downbonded ground pads
and `tank_p/tank_n` on two spirals "placed at assembly" (`$P/analog/rf_rx/README.md:47-51`). The pad list has no such
pads (`$P/spec/contract.json:77` mentions them only), MASTERS has no spiral, and BIND shows all four pins UNBOUND: the
LNA has neither a source return nor a load. NL:57-58 also puts both mixers on `rf_out` and leaves `rf_outq` open,
where the chain bench uses one output per mixer (`tb.py:889,893-894`). `lobias` (`lna.bias.lo`) and rxmix `hib` have no
register field, so the duplex power assumption in IC:1222 cannot be enforced. Owner: pads/assembly (2 pads, 2 spirals,
rf_outq), digital (2 bits + validator), rf_rx (fix `README.md:131`).

**F6. Converter references are not connected in the assembly netlist (RX; TX unaffected).** `core_bias` produces VREF0
and VCM (`$P/integration/core_bias.py:82,133`) and says the parent binds them to `refbuf.VREF0` and `adc_*.VCM`
(:143-144). NL puts `refbuf.VREF0` on `VREF0_CONV` and the ADCs on `VCM_CONV` (NL:53,64-65) but leaves
`core_bias.VREF0` on `ATBN_master_vref0` (in BIND's dangling list) and `core_bias.VCM` on `ATBN_master_vcm`. Result:
refbuf reference and ADC VCM float; only ATB leaves touch them. Same pattern for the refpad `VCM` pin (`REF_VCM`, no
driver). Reproduce with the net dump in `scratch/reviews/mode-walk/rf/` notes below or by grepping BIND for those
nets. Owner: assembly (three binding rules).

**F7. Internal (autonomous) LO is not on the chip.** Known as LO3, listed so nobody plans on it: QVCO, `lo_mmd`,
`lo_pfdcp`, `lo_lf`, `lo_obs` are laid out but not in INV MASTERS; the bias output for the VCO is fabricated with EN
tied low (`core_bias.py:123-124`) and there is no bias output for `lo_pfdcp.IBIAS`; all `rfpll.config.*` fields are
dropped; there is no sigma-delta or band-search RTL; the only thing on `LOI_*` is `pt_polyphase` with an unbound input,
CMOS-level outputs that `lo_ext`'s CML input was never benched with, and a failing extraction (IC:553). Owner: timing
+ coordinator (declare the mode absent for this tapeout or schedule it).

### DEGRADED

**D1. The mixers were never verified with the LO they will get; the RX mixer loses 5-16 dB (RX, duplex; TX
unverified).** Every rf_rx bench drives the passive quad with a 0/VDD square (`tb.py:453-454,867,1076,1226`,
`README.md:70,612`). `pt_lo_ext` delivers a sine about VB = 0.739 VDD with the switch source at VDD/2, and its pass
criterion is only peak Vgs >= 0.9 V (`lo_ext_pad.py:258`; ext window on-level 0.91-1.16 V, IC:551; CML 1.05-1.11 V,
IC:549). With the body at VSS and the source at 1.65 V the 30/0.28 switch is 111 ohm at Vgs 1.65 V but 348 ohm at 1.1 V,
626 ohm at 1.0 V and 1.7 kohm at 0.9 V (DC points, tt). Transient on the quad alone (same source as `tb.rxmix_tran`:
300 ohm/leg, 4 pF, ideal virtual grounds, tt/27 C, 2.4 GHz, IF 50 MHz): relative to the bench square LO the IF
current is -4.6 dB at peak Vgs 1.16 V, -7.3 dB at 1.05 V, -16.2 dB at 0.90 V; a rail-to-rail sine is -2.4 dB.
Reproduce: `cd scratch/reviews/mode-walk/rf && python3 mixlo.py` (about 6 min on the loaded machine; output saved in
`mixlo.out`; `ron.cir` for the DC points). Limits: quad only, not the LNTA tank source or the real TIA, one corner;
the chain loss will differ in detail but the switch is under-driven in every case, and chain NF is already 14.1 dB
against 4.1 dB with the ideal LO (`README.md:195`). The TX Gilbert quad was benched only with 0/3.3 V and 0/2.5 V
squares (`simulate.py:116-122`, `run_benches.py:335`); I did not simulate it. Owner: rf_rx + timing jointly (one bench
with extracted `lo_ext` driving the extracted mixers; then either more LO swing, a lower mixer VCM, or a PMOS/TG quad),
rf_tx (rerun `chain_deck` with the sine).

**D2. One CONV_CLK for both converters.** Halfband TX needs rf_tx_clk = 80 MHz (`pt_digital.sv:89-91`) while the ADC
runs at 40 or 20 MHz; `pt_clockmux` has one converter output and the analog side has no divider for it. Duplex is
limited to equal ADC/DAC rates (interpolator bypass). Also `spec/analog-architecture.json` DAC_CLOCK tops out at
39.06 MHz against SP-03's 80 MS/s. Owner: timing, spec.

**D3. DAC into the shared filter was benched at a fifth of full scale and with the wrong load.** DAC full scale is
+-0.98 V differential about 1.62-1.77 V (`converters/README.md:174-175`), so a leg reaches ~2.2-2.3 V; `tx_in` enters
through an NMOS-only switch (`bbfilter_i.spice:769`) whose resistance triples there, and the TX-direction bench uses
0.2 V (`tb.py:1006`). The DAC bench load is 100 fF with no resistive load (`benches.py:324`), while the filter's
stage-1 input conductance sits across the DAC's 1 kohm legs. Expect a gain error and some odd-order distortion at full
scale; no number. Owner: rf_rx + converters (one joint bench: extracted DAC -> extracted bbfilter in TX direction at
-1 dBFS).

**D4. BB tap is wired to the wrong nodes in the assembly.** Cell intent: `bb_tap.in <- bbfilter.obs`, `bb_tap.inj ->
bbfilter.inj` (`rf_rx/README.md:137`). NL:79-80 puts `bb_tap.in` on the ADC input net and `bb_tap.inj` on the DAC output
net and leaves the filter's obs/inj pins open. `observe_rx_mixer`/`observe_rx_pga` cannot work, inject lands on the DAC
node instead of the filter core input, and the tap's follower gate is a permanent extra load on the ADC input. This is
the external-ADC / external-baseband fallback path (learning/fallback-first tapeout). Owner: assembly; digital for the
`debug.bb_tap.mode` -> `obs_sel/inj/obs_en/inj_en` decode, which also does not exist.

**D5. rfdriver mute has two sources and no gate.** The transport's `rf_mute` (`pt_core.sv:261`) and the register
`rfdriver.mute.mute` (reset 1) must both mute; the cell has one pin and BIND leaves it UNBOUND. Tied to either one
alone, either the scheduler cannot mute or the reset state is unmuted-when-streaming. Owner: digital (export the OR as
a level), assembly.

### COSMETIC

- **C1.** `rf_rx/README.md:131` still says `rf_out` feeds both mixers; `timing/README.md:61` port list for `pt_lo_ext`
  lacks CMLSEL; `rf_rx/README.md:153` calls the PGA code `gain[3:0]`.
- **C2.** Enable semantics differ: analog READMEs say `state != off` (`rf_rx/README.md:142,145`), RTL uses
  `state == active` (`pt_digital_macro.sv:161-186`). `adc_*.config.enable`, `dac_*.config.enable`, `refbuf.enable.enable`,
  `txmix_*.enable.enable`, `txsum.enable.enable`, `clockmux.config.rf_source`, `refinput.select.branch`,
  `clocktree.config.sample_divider/sample_enable/rf_host_*`, `debug.clk_select.rf_lo` are on the bus with no consumer in
  any cell, RTL decode or NL rule. `refbuf.OVR` has a field (`debug.bias_override.refbuf`) but no binding.
- **C3.** `pt_chip.sv` does not connect the macro's `en_eff`, `island_off`, `rf_tx_clk_out` outputs.
- **C4.** LO pad bench used unequal pad families for I and Q; v4 places `refpad` on both (INV:408-409). Rerun
  `lo_ext_pad.py` before publishing B3.

---

## 3. What I could not trace

- Anything inside `pt_analog_physical`: it does not exist. All "assembly" verdicts are about NL's rules.
- Whether the converter `clkrx` accepts a rail-to-rail single-ended CMOS clock (CLKN at a reference). Not simulated.
- ADC behaviour with a 50 % clock: inferred from published conversion times, not simulated.
- TX Gilbert mixer gain, Psat and LO leakage with the real LO waveform (D1): not simulated.
- `rx_direct` path (rxmix TIA driving the ADC directly): no bench on either side.
- ADC input common-mode tolerance away from 1.65 V, and one refbuf loaded by two interleaved ADCs.
- RF_TX pad clamp behaviour at 4.1 V peaks and the RF_RX match with the LNTA: took the pads README at its word.
- Island isolation of ADC outputs into the core-rail macro (`ISO_conv/ISO_rf/ISO_pll` are dangling in BIND).
- `rf_trim[15:0]`, `calibration_trial`, `calibration_above_target`, `mode8`, `enable` at the analog boundary: no analog
  consumer found; did not chase further.
- The LNA attenuator level table used by the fast-gain RTL after RC-16j moved the attenuator across the tank.
- GX-9 TX->RX isolation, IX-6 direction-change timing, IX-7 loopback: no artefacts found.
- `refbuf.READY` and lock/status paths into `analog_status`.
- rf_rx `generated/` is modified in the working tree (git status); I read the working-tree files, which may be ahead of
  the last committed evidence.

Scripts and outputs: `scratch/reviews/mode-walk/rf/mixlo.py`, `mixlo.out`, `ron.cir`.
