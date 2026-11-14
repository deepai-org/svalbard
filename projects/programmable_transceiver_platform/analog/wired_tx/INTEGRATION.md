# Wired TX subsystem: exact pins and connection intent for chip-top integration

Interface rows: WT25 (enable / clock / reset), WT26 (TX ring), WT27 (TMDS tie-off), WT28 (fallback), WT29 (real ring
phases), WT30 (idle), WT31 (2.7-3.24 Gb/s) in `scratch/reviews/interface-changes.md`. The USB data path is in
`USB-INTEGRATION.md`.

Pin order below is the `.subckt` order of the published netlists. "Published" = GDS + extracted netlist + DRC / LVS
in `generated/`. Everything not marked published must NOT be instanced.

## 1. Instances

| Instance | Master | Files | State |
| --- | --- | --- | --- |
| `wiredtx` | `pt_wiredtx` | `analog/wired_tx/wiredtx.spice`, `generated/wiredtx.{gds,ext.spice}` | published (quarter-rate core, line <= 2.5 Gb/s), 546.9 x 454.2 um |
| `pll_tx` | `pt_pll_ring_core` | `analog/timing/pll_ring_core.spice`, `generated/pll_ring_core.*` | published by timing |
| `pll_vreg` | `pt_pll_vreg2` | `analog/pll_vreg/generated/pt_pll_vreg2.*` | published |
| `pad_wire_tx` | `tx_protected_pad` (`pad_txpad`) | `analog/pads/generated/stress-safe-families/wired-transmit/` | published by pads; 0.6x switch resize and TMDS-branch removal requested (WT24, WT27) |
| `steer_main_p/n`, `steer_post_p/n` | `tx_steering_buffer_flat_physical` | `analog/pads/generated/steering-buffer-compact/` | published; INTERIM, good to about 1.5 Gb/s only (WT24: drops pulses < 400 ps) |
| `predrv_main`, `predrv_post` | `tx_cml_predriver_flat_physical` (`wt24_tr7`) | `scratch/pads-wt24/lay_tr7/` | NOT published; replaces the four steering buffers when it is |
| `tx_interlock` | `tx_mode_interlock_flat_physical` | `analog/pads/generated/transmit-control-candidate/thick-logic/` | published by pads |
| `tx_term_buffer` (`attached_tx_buffer`) | `buffer_compensated_flat` | `analog/pads/generated/termination-buffer-candidate/compact-array/` | published by pads |
| `rx_wtx_ext` | `pt_diff_clk_rx` | `analog/timing/generated/diff_clk_rx.*`, wrapper `analog/wired_tx/wtx_ext_rx.spice` | published by timing; fails from 0.5 Gb/s (TIM-08) |
| `wtx_fallback_control` | `pt_wtx_fallback_control` | `analog/bringup_control/` | published; decodes the external-data request (WT28) |
| `hsbias` | `pt_wtx_hsbias` | `analog/wired_tx/hsbias.spice`, `generated/hsbias.*` | published; see `USB-INTEGRATION.md` |

## 2. `pt_wiredtx` (published)

```
.subckt pt_wiredtx WTX_PH0 WTX_PH90 WTX_PH180 WTX_PH270 MODE_H MODE_F D0 .. D39 WORD_CLK WORD_CLK40 SER_EN WTX_EXT DX
+ POST_POL EN_MAIN EN_POST ISLAND_OFF IBIAS MAIN_CODE0 .. MAIN_CODE7 POST_CODE0 .. POST_CODE7 CMD_MAIN_P CMD_MAIN_N
+ CMD_POST_P CMD_POST_N MAIN_BIAS POST_BIAS WTX_EXT_DATA ATB_NBIAS ATB_PBIAS VDD VSS
```

All inputs are MOS gates on the wired rail. A core-domain signal crossing into the block needs no clamp when the
island is off (gate only); every OUTPUT that goes to the core domain needs a wired iso clamp.

| Pin | Dir | Connect to | Notes |
| --- | --- | --- | --- |
| `VDD`, `VSS` | supply | `RAIL_wired` (VDD_WIRED_SW), ground | supply current per rate: `generated/wiredtx-sims.json` |
| `WTX_PH0`, `WTX_PH90`, `WTX_PH180`, `WTX_PH270` | in | `pll_tx.PH0`, `PH2`, `PH4`, `PH6` directly | NOT through the clockmux. Four routes length- and load-matched, shielded from each other. PROVISIONAL budget: 60 fF and 30 ohm each are the values the real-ring bench used (section 6), and at those values the block FAILS at ss (WT29); a matching number (target 10 ps) has no evidence yet. The phases swing to the ring supply (0.9 x rail) and cross pll island -> wired island without a clamp: the ring must be disabled (phases clamped low by its EN) whenever the pll island is off and the wired island is on |
| `MODE_H`, `MODE_F` | in | decode of `consolidation.wiredtx_stage.rate_mode[1:0]`: 0 -> 00 (x1), 1 -> 10 (x2), 2 -> 01 (x4) | static; only places the postcursor one LINE bit late. Change only with `SER_EN` = 0. `bits_per_cycle` is not used by this block |
| `D0..D39` | in | `digital.wire_tx_data[39:0]` (D0 = bit 0 = first on the line) | timing: WT20 / WT25(5). In x2 / x4 the digital must present every user bit 2 / 4 times (WT19: not in the RTL yet) |
| `WORD_CLK40` | out | wired iso clamp -> `digital.wire_tx_clk` | core rate / 40, 50 % duty, <= 62.5 MHz; the only clock of that domain |
| `WORD_CLK` | out | wired iso clamp -> `fc_src[*]` / `WCLK_OBS` mux only | core rate / 20; must not be on the same net as `wordclk.WORD_CLK` or `digital.ct_word_clk` |
| `SER_EN` | in | NEW macro output: `(wiredtx.state.state == active) & island_on[wired] & tx_ring_ready & !debug.wtx_ext.enable` | WT25; not `ct_ser_run`. `tx_ring_ready` does not exist yet (frequency check on `pll_tx.FBCK`, or a timer once timing states the ring lock time) |
| `WTX_EXT` | in | `debug.wtx_ext.enable` | selects DX (break-before-make against the serializer) |
| `DX` | in | `rx_wtx_ext.OUTN` (receiver legs swapped) -> debug iso clamp -> wired iso clamp -> here | tie low when the fallback receiver is not instanced |
| `POST_POL` | in | `wiredtx.config.post_polarity` (analog bus bit 457, reset 0) | 0 = de-emphasis (POST opposes MAIN), 1 = MLT-3 / 100BASE-TX (same sign) |
| `EN_MAIN`, `EN_POST` | in | `tx_interlock.EN_MAIN`, `.EN_POST` | they also gate the bias: IBIAS is used only while one of them is high. `EN_POST` should be requested only when `postcursor_code != 0` or `post_polarity` = 1 (power) |
| `ISLAND_OFF` | in | `island_off[wired]` (core domain) | high: CMD outputs and both tail biases clamped to VSS |
| `IBIAS` | in | 10 uA SOURCED into the pin from the wired bias bank (`BIAS_wiredtx`) | NMOS diode behind a switch; bank output enable = `EN_MAIN | EN_POST` |
| `MAIN_CODE0..7` | in | `wiredtx.config.current_code[7:0]` (reset 109 = 9.05 mA; 255 = 21 mA; LSB about 83 uA at the pad tail) | also the TMDS code (102 / 125) |
| `POST_CODE0..7` | in | `wiredtx.config.postcursor_code[7:0]` (reset 0) | |
| `CMD_MAIN_P`, `CMD_MAIN_N`, `CMD_POST_P`, `CMD_POST_N` | out | one `steer_*` buffer each (`IN`), buffer `OUT` -> pad `MAIN_P`, `MAIN_N`, `POST_P`, `POST_N`. With the pre-driver: `predrv_main.INP/INN`, `predrv_post.INP/INN` | never straight to the pad gates (about 1 kohm source into 0.5-0.9 pF). MAIN: logic 1 on the line = `CMD_MAIN_N` high = `V(PAD_P) > V(PAD_N)` (the steering buffer is non-inverting; `MAIN_N` sinks `PAD_N`). POST with `POST_POL` = 0 is the opposite sense, one line bit later (`CMD_POST_P` high for the delayed 1). Routes <= 100 fF, P/N matched. `pt_usb_txdrv.CMD_P/N` also hang on `CMD_MAIN_P/N` (about 10 fF per leg, cell placed beside these outputs; `USB-INTEGRATION.md`, row USB-D5); the effect of that tap on the 2.5 Gb/s CMD eye has not been run |
| `MAIN_BIAS`, `POST_BIAS` | out | pad `MAIN_BIAS`, `POST_BIAS` | gate-voltage mirror, ratio 16 (diode 2 x 20/1, pad tail 32 x 20/1): keep the two blocks adjacent, VSS returns joined at the pad |
| `WTX_EXT_DATA` | out | wired iso clamp -> `wire_analog_status[12]` | `DX AND WTX_EXT` (toggles only in fallback mode), observation |
| `ATB_NBIAS`, `ATB_PBIAS` | out | ATB leaves (node 26 `wiredtx_bias`; second leaf for PBIAS) | NBIAS = reference diode, PBIAS = PMOS gate of the MAIN DAC only |

Not on the block (digital signals without an analog consumer, see WT25 / WT30): `ct_ser_run`, `ct_word_load`,
`ct_bit_phase`, `ct_qualified`, `wire_tx_request` (tie 1), `wire_tx_valid`, `wire_idle` (see section 5).

## 3. TX ring and its regulator

```
.subckt pt_pll_ring_core REF EN N4 N8 HOLD IBIAS PH0 PH1 PH2 PH3 PH4 PH5 PH6 PH7 LOCK FBCK REFO ATB_VCTRL BAND VDD VSS
.subckt pt_pll_vreg2 VIN VOUT_TX VOUT_CDR VSS BYP_TX BYP_CDR ATB_OUT ATB_G
```

| Pin | Connect to | Notes |
| --- | --- | --- |
| `pll_tx.VDD` | `pll_vreg.VOUT_TX` | ring range and phase data exist only on the regulated supply: 2.57-2.95 V at ss/32 over VIN 3.05-3.35 V and 3-8 mA (`analog/pll_vreg/evidence/`), i.e. 0.84-0.88 x the pll rail, not a fixed 0.9 x |
| `pll_tx.REF` | `ref_clk` (REF_IN receiver output) | reference = ring / N |
| `pll_tx.EN` | `ring_l.config.enable & island_on[pll] & vreg_tx_ok` | WT26; not `rfpll.state` (en_eff[11]). |
| `pll_tx.N4`, `N8` | decode of `ring_l.config.modulus[1:0]` (values 16, 8, 4) | 0: both low (/16); 1: `N8`; 2: `N4` |
| `pll_tx.HOLD` | VSS | CDR hand-over pin, unused on the TX ring |
| `pll_tx.BAND` | `ring_l.config.band` (reset 1) | 0 for ring <= about 480 MHz |
| `pll_tx.IBIAS` | 10 uA sourced, pll bias bank `BIAS_pll_ring_tx` | |
| `pll_tx.PH0/2/4/6` | `wiredtx.WTX_PH0/90/180/270` | |
| `pll_tx.PH1/3/5/7` | matched dummy load (same route length, open end) | become live with the eighth-rate core |
| `pll_tx.FBCK` | `fc_src[0]` (pll iso clamp) | frequency check = `tx_ring_ready` source |
| `pll_tx.LOCK` | `analog_status[0]` | status only (invalid at the top of the range) |
| `pll_tx.REFO` | open | |
| `pll_tx.ATB_VCTRL` | ATB leaf `pll_vctrl` | high impedance node: leaf must be off in operation |
| `pll_vreg.VIN` | `RAIL_pll` | |
| `pll_vreg.BYP_TX`, `BYP_CDR` | `pllvreg.config.tx_bypass`, `.rx_bypass` (reset 1) | bypass = ring on the raw rail: phases full swing, 33 ps peak supply jitter (pll_vreg README) |
| `pll_vreg.VOUT_CDR` | `pll_cdr.VDD` | wired RX's ring |
| `pll_vreg.VSS` | ground | |
| `pll_vreg.ATB_OUT`, `ATB_G` | ATB sense leaves only | `ATB_G` is the pass-device gate: forcing it overrides the regulator; never select a force leaf on it in operation |

## 4. Pad, drivers of the pad gates, interlock, termination

```
.subckt tx_protected_pad PAD_P PAD_N VDD VSS CASCODE MAIN_P MAIN_N MAIN_BIAS POST_P POST_N POST_BIAS TMDS_P TMDS_N
+ TMDS_BIAS DETECT_ENABLE DETECT_PBIAS TERM_ENABLE TERM_VCM ATB_ESD_RAIL
.subckt tx_steering_buffer_flat_physical VDD VSS IN OUT
.subckt tx_mode_interlock_flat_physical VDD VSS REQ_MAIN REQ_POST REQ_TMDS REQ_DETECT REQ_TERM RESET QUALIFIED SUPPLY_OK
+ CONFLICT VALID EN_MAIN EN_POST EN_TMDS EN_DETECT EN_TERM
.subckt buffer_compensated_flat VDD VSS REF BIAS OUT ENABLE
.subckt tx_cml_predriver_flat_physical VDD VSS INP INN OUTP OUTN EN T0 T1        (NOT published)
```

| Pin | Connect to | Notes |
| --- | --- | --- |
| pad `PAD_P`, `PAD_N` | bond pads WIRE_TX_P / WIRE_TX_N | |
| pad `VDD`, `VSS` | `RAIL_wired`, ground | |
| pad `CASCODE` | `RAIL_wired` | as in every wired TX bench and the fallback fixture |
| pad `MAIN_P/N`, `POST_P/N` | `steer_*` `OUT` (later `predrv_*` `OUTP/OUTN`) | |
| pad `MAIN_BIAS`, `POST_BIAS` | `wiredtx.MAIN_BIAS`, `.POST_BIAS` | |
| pad `TMDS_P`, `TMDS_N`, `TMDS_BIAS` | VSS | WT27; branch unused |
| pad `DETECT_ENABLE` | `tx_interlock.EN_DETECT` | |
| pad `DETECT_PBIAS` | `RAIL_wired` (detect source off) unless pads state a bias source | pads to confirm |
| pad `TERM_ENABLE` | `tx_interlock.EN_TERM` | |
| pad `TERM_VCM` | `tx_term_buffer.OUT` | 1.65 V in the wired TX benches (ideal source, 2 ohm); VSS in the fallback fixture (TMDS-style, termination off). The pad netlist has `X235 TERM_VCM VSS VSS ppolyf_u_1k` 2 x 2 um (`physical.spice:255`), which reads as about 1 kohm to VSS = about 1.65 mA of static load on the buffer: pads to confirm |
| pad `ATB_ESD_RAIL` | ATB leaf or 1 Mohm to VSS | |
| `tx_term_buffer.REF`, `.BIAS`, `.ENABLE` | pads to state (REF = 1.65 V source, bias branch, enable = `EN_TERM`) | no source is bound in any netlist (mode-walk section 1) |
| `tx_interlock.REQ_MAIN` | normal: `(wiredtx.state == active) & (txpad.config.branch in {serial (1), tmds (2)})` (NOT `detect` (3)); fallback: `wtx_fallback_control.TMDS_REQUEST` (WT28) | TWO sources and no combiner exists: an OR on the wired rail (or a second decode output on `pt_wtx_fallback_control`) must be defined; owner open (chip-top / bring-up control) |
| `tx_interlock.REQ_POST` | `REQ_MAIN & (postcursor_code != 0 | post_polarity)` | |
| `tx_interlock.REQ_TMDS` | VSS | `EN_TMDS` output left open |
| `tx_interlock.REQ_DETECT`, `REQ_TERM` | `txpad` detect / termination request bits | digital: `rtl/pt_tx_pad_sequence.sv` exists but is instantiated nowhere |
| `tx_interlock.RESET`, `QUALIFIED`, `SUPPLY_OK` | `island_off[wired]`, `island_on[wired]`, `island_pgood[wired]` | as the fallback fixture |
| `steer_*` `VDD`, `VSS` | `RAIL_wired`, ground | four instances (MAIN P/N, POST P/N); outline 54.6 x 159.0 um each (PD46) |
| `predrv_*` `EN` | `EN_MAIN` / `EN_POST` | when published; `T0`, `T1` = NEW field `wtx.predrv_trim[1:0]` (reset 1), shared by both |

### Fallback receiver `rx_wtx_ext` (`pt_diff_clk_rx INP INN EN SE OUTP OUTN PRESENT ATB_DET VDD VSS`)

| Pin | Connect to | Notes |
| --- | --- | --- |
| `INP`, `INN` | protected WTX_EXT_N, WTX_EXT_P (legs SWAPPED) | as `wtx_ext_rx.spice` and the fallback fixture |
| `EN` | `digital.rx_en_wtx_ext` (debug iso clamp) | |
| `SE` | VSS | differential mode |
| `OUTN` | debug iso clamp -> wired iso clamp -> `wiredtx.DX` | `OUTP` open |
| `PRESENT` | debug iso clamp -> status | diagnostic only; must not gate the output driver |
| `ATB_DET` | ATB leaf | |
| `VDD`, `VSS` | `RAIL_debug`, ground | the receiver is on the DEBUG island, the serializer on the wired island |

## 5. Electrical idle, repetition, request (MW-35)

* The published block has NO idle input. With `EN_MAIN` = `EN_POST` = 0 both legs are off and the lines sit at
  `TERM_VCM` (differential 0, common mode steps up by I x 25 ohm, 0.2-0.5 V; the enables go through the interlock
  and the bias switch; their settling time has not been measured). That is a power-down, not a protocol idle: SATA OOB (106.7 ns bursts) and
  PCIe electrical idle are NOT supported today. Planned: pin `IDLE` on the CMD stage (both switch gates driven to
  the same level, tail current kept, differential 0 with unchanged common mode, entry / exit within one word),
  driven by `digital.wire_idle` through the wired domain. Row WT30. Until then tie nothing to `wire_idle`.
* Bit repetition x2 / x4 is the digital's (WT19); `rate_mode` selects it and drives `MODE_H/MODE_F`.
* `wire_tx_request`: no analog source, tie high (WT25(6)).

## 6. Real-neighbour evidence for this pin list (source = extracted ring, load = pad chain)

Single-point observations (nominal extraction, CMD pins, about 100 bits each; `generated/wiredtx-realring.json`,
benches `sim_ringsrc.py` / `sim_realring.py`, row WT29):
* ss/32/3.15 V, ring supply 2.69 V, 626 MHz (2.5 Gb/s): 11 errors / 101 bits. FAIL.
* same harness, ideal full-rail phases: 0 errors, eye 240 ps.
* tt/27/3.3 V, ring supply 2.925 V: 0 errors / 101 bits, eye 226 ps (one point; not a qualification).
Not yet run: other ring supplies (2.57 V, 2.9 V, bypass), ff / sf / fs, pessimistic values, a line-level result
through the pad-gate drivers. The 3.24 Gb/s chain results are in WT31.

## 7. Planned pin delta (eighth-rate core, NOT published; do not bind yet)

`pt_wiredtx` with `wtx_serq8` (2.4-3.24 Gb/s at x1, ring 300-405 MHz):
* `WTX_PH0/90/180/270` -> eight pins `WTX_PH0, 45, 90, 135, 180, 225, 270, 315` = `pll_tx.PH0..PH7` (all matched);
* mode pins `MODE_H`, `MODE_F` keep their names; repetition factors become 1 / 2 / 4 / 8 (a third pin or a
  re-coded pair; decided at publication);
* the 40-bit word is loaded at once (no 40 -> 20 mux): D-bus timing becomes one window, WT20 will be restated;
* `WORD_CLK40` = ring / 5 (<= 81 MHz);
* new pins `IDLE` (section 5) and, with the pre-driver, nothing else on this block.
Area: core macro as built 767.6 x 458.8 um (0.352 mm2) against the `tx8_rsv` booking 450 x 445 um (AP4-2): over.

## 8. Demands on other owners (summary; details in the rows)

| Owner | Demand |
| --- | --- |
| digital | SER_EN equation, `wire_tx_clk` = WORD_CLK40, `wire_tx_request` tie, `tx_ring_ready`, binding of the existing `ring_l.config.enable/modulus/band` and `wiredtx.config.post_polarity`, NEW `wtx.predrv_trim`, the `REQ_MAIN` combiner, decode of `rate_mode` -> MODE pins, repetition x2 / x4, interlock requests (`pt_tx_pad_sequence`), SDC including clamp + route |
| timing | PH7 (and odd-phase) skew of `ct_phbuf8` in `pt_pll_ring_core`, duty cycle at ss (WT29); reference divider or reference list; `pt_diff_clk_rx` data rate (TIM-08) |
| pads | 0.6x MAIN/POST switch resize + TMDS branch removal in one re-layout; TX termination trim (WT24); sources of `tx_term_buffer.REF/BIAS`, `DETECT_PBIAS` |
| chip-top | bindings above; delete `netlist.py` TMDS rules; instance `pll_tx`, `pll_vreg`, the four steering buffers, interlock, termination buffer; iso clamps on WORD_CLK40, WORD_CLK, WTX_EXT_DATA |
| board | one reference frequency per rate family (WT26(5)) |
