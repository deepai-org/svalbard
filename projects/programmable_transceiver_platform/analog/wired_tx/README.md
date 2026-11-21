# Wired-TX family (`analog/wired_tx`)

Serializer, pre-driver gating and tail-bias DACs (`pt_wiredtx`, and its successor `pt_wiredtx8`), the USB pre-driver
(`pt_usb_txdrv`), the USB HS bias DAC (`pt_wtx_hsbias`) and the fallback receiver instance (`wtx_ext_rx`). Ring
phases come from the shared `pt_pll_ring_core` (owner: wired RX / timing); the pad, steering buffers, interlock and
termination are `analog/pads`. This README is the pin-level connection statement for chip-top (sections 2-4).
Nothing here is qualified. Numbers are from extracted netlists (Magic C) unless marked; `generated/*-evidence.json`
is the record. Interface rows (`WTnn`, `USB-Dn`) are in `scratch/reviews/interface-changes.md`. Working notes and the
resume point for a successor: `scratch/wired_tx/STATUS.md`.

Sections: 1 Blocks and instances · 2 `pt_wiredtx8` pins · 3 `pt_wiredtx` (legacy) pins and integration ·
4 USB · 5 Rules and demands on other owners · 6 Evidence · 7 Reproduce · 8 Open items.

Pin order in the `.subckt` lines is the order of the netlists. "Published" = GDS + extracted netlist + DRC / LVS in
`generated/`. Everything not marked published must NOT be instanced.

## 1. Blocks and instances

| Block | Published outline | DRC (Magic / KLayout) | LVS | Verified function (evidence) |
| --- | --- | --- | --- | --- |
| `pt_wiredtx` (quarter-rate CMOS core `wtx_serq4c`, CMD gating, MAIN / POST tail DACs) | 546.9 x 454.2 um = 0.248 mm2 | 0 / 0 | unique | ideal phases: 2.5 Gb/s 0 errors at ss/32/3.15 and ff/22/3.35 at the CMD pins (`generated/wiredtx-evidence.json`). Real ring phases: 0 errors at tt, **11 errors / 101 bits at ss/32/3.15** (`generated/wiredtx-realring.json`) |
| `tmds` | configuration of `pt_wiredtx` (TMDS levels through the MAIN branch) | (wiredtx) | (wiredtx) | 1.485 Gb/s tt: eye 1050 mV / 604 ps, 0 errors (`generated/wiredtx-evidence.json`) |
| `pt_usb_txdrv` | 116.48 x 270.06 um = 31,457 um2 | 0 / 0, precheck clean | unique | table in section 4 (`generated/usbdrv-evidence.json`) |
| `pt_wtx_hsbias` | 125.8 x 76.0 um = 9,552 um2 | 0 / 0 | unique | 0-0.58 V full scale at tt, monotonic at all corners, 1 LSB settling 0.47 us (`generated/usb_hs_bias-evidence.json`) |
| `wtx_ext_rx` | instance of timing's `pt_diff_clk_rx` (`wtx_ext_rx.spice`) | timing | timing | through the extracted receiver: 5 / 43 errors at 0.5 Gb/s, no output at 2 Gb/s (`generated/wtx_ext_rx-evidence.json`; risk TIM-08) |

Not published (must not be instanced): the new block top `pt_wiredtx8` and its parts (below), the earlier eighth-rate
core `wtx_serq8` (`serq8_macro.py`), the laid-out mux revision 2 (`mux8.py`, `mux8_layout*.py`, to be deleted when
revision 3 publishes) and the CML pre-driver `wt24_tr7` (`scratch/pads-wt24/`).

Chip-top instances around the wired TX:

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
| `hsbias` | `pt_wtx_hsbias` | `analog/wired_tx/hsbias.spice`, `generated/hsbias.*` | published; see section 4 |

### Ownership

| Item | Owner |
| --- | --- |
| Serializer, final mux, pre-driver gating, ext-data select, tail-bias DACs, HS bias DAC, USB pre-driver | this family |
| Pad tails / switches, cascodes, terminations, detect, interlock, protection, steering buffers | `analog/pads` |
| Ring PLL and its phases, `pt_diff_clk_rx` | `analog/timing` (wired RX owner) |
| Pattern generator / checker, mode decode, `SER_EN`, bit repetition, USB logic | `rtl` |

## 2. `pt_wiredtx8` (staged master, not yet published)

`pt_wiredtx8` = `wtx_ser8d` (40-bit word into eight streams) + `wtx_mux8` (8-phase muxing pre-driver that drives the
pad's MAIN / POST switch gates) + `wtx8_aux` (glue, two tail DACs, CMOS tap for `pt_usb_txdrv`) + phase buffers
(`wtx8_phbuf`) + decap. Schematic `wtx8_top.py` (`generated/fast/pt_wiredtx8.spice`). It replaces `pt_wiredtx`, the
four steering buffers and the pre-drivers when it publishes; the block must sit at the pad (its `MAIN_P/N`,
`POST_P/N` wiring is part of the 1 pF output node). Placement and phase access: section 5. Circuit descriptions are
the docstrings of `wtx_mux8.py`, `ser8d_macro.py`, `wtx8_top.py`.

| Cell | Outline | DRC (Magic / KLayout) | LVS on the GDS read from disk | State |
| --- | --- | --- | --- | --- |
| `wtx_ser8d` | 744.1 x 197.7 um = 0.147 mm2 | 0 / 0 | unique, 4 negative controls fail (first hop table); the final hop table has only the generator's own DRC 0 / LVS unique | `scratch/wired_tx/s13/ser8d/REPORT.md`; re-run `verify.py` |
| `wtx_mux8` revision 3 | 324.6 x 163.4 um = 0.053 mm2 | 0 / 0 | unique, 4 negative controls fail, antenna 0 | `scratch/wired_tx/s13/mux3/REPORT.md`; EM table passes at 26 mA per bank (zero margin at 30.1 mA) |
| `wtx8_aux` | side cell 69.8 x 118.5 um + tap row in the mux corner | 0 / 0 | unique, 2 negative controls fail | same report |
| `pt_wiredtx8` (first pass) | 744.1 x 471.3 um = 0.351 mm2 bounding box, of which a 110 um seam (0.082 mm2) and a free 147 x 154 um rectangle | 0 / 0 | unique against the schematic WITHOUT the phase buffers, 3 negative controls fail | `scratch/wired_tx/s13/top/REPORT.md`. **The schematic is ahead of this layout** (`wtx8_phbuf` added afterwards); the second layout pass (seam <= 40 um, D pins on the bottom edge, header feed, bias pins to the pad edge) was started and NOT finished: `scratch/wired_tx/s13/top/*pass2-wip.py`, and `wtx_mux8_layout.py` carries unverified edits of that pass |

Extraction: capacitance-only netlists `generated/fast/*.ext.spice`; `*.rc.spice` add resistance (Magic extresist on a
subset of nets plus drawn-width resistance of the mux buses, gate trunks and the top-level phase / stream / supply
wires). No simulation has used the R+C netlists yet.

### Pins

```
.subckt pt_wiredtx8 PH0 .. PH7 D0 .. D39 WORD_CLK40 SER_EN IDLE IDLE_MODE WTX_EXT DX POST_POL EN_MAIN EN_POST ISLAND_OFF
+ TAP_EN IBIAS MAIN_CODE0 .. MAIN_CODE7 POST_CODE0 .. POST_CODE7 TR0_0 .. TR7_3 MAIN_P MAIN_N POST_P POST_N MAIN_BIAS
+ POST_BIAS TAP_P TAP_N TX_RUN WTX_EXT_DATA ATB_NBIAS ATB_PBIAS ATB_AVGP ATB_AVGN VDD VSS
```

| Pin | Dir | Connect to | Notes |
| --- | --- | --- | --- |
| `PH0..PH7` | in | `pll_tx.PH0..PH7` directly | eight matched routes (the mux and the stream registers both hang on them); swing = ring supply. The stream-register path enters through NAND2(PH k, SER_EN) (`wtx8_phbuf`), so **SER_EN must be low while the pll island is off**: the PH inputs then float without crowbar current (<= 1 uA per buffer at ff 3.63 V hot). Ring load per PH (block extraction, NAND input included) 36.0-37.6 fF, spread 1.6 fF; ring route budget 30 ohm + 75 fF per phase (TIM-23). Access: Metal5 lanes from the block's top edge (section 5, WT47) |
| `D0..D39` | in | `digital.wire_tx_data[39:0]`, D0 first on the line | the whole 40-bit word is loaded at once; launch about a quarter word period after the `WORD_CLK40` rise (benches: 0.25 T) |
| `WORD_CLK40` | out | wired iso clamp -> `digital.wire_tx_clk` | ring / 5 (60-81 MHz), duty 2/5 |
| `SER_EN` | in | as `pt_wiredtx` (section 3) | also gates the eight phase buffers (NAND2 with PH k): low whenever the pll island is off |
| `IDLE`, `IDLE_MODE` | in | `digital.wire_idle`; NEW static field `wtx.idle_mode` | data gating, asynchronous. `IDLE_MODE` 0: both pad gates of each pair at the supply; 1: both legs of the conducting slice on (gates at mid level). Differential 0 in both |
| `WTX_EXT`, `DX` | in | `debug.wtx_ext.enable`, fallback data (section 3, fallback receiver) | `DX` = 1 gives `V(PAD_P) > V(PAD_N)`. With the ring running the slices work as usual on `DX`; with the ring stopped all eight MAIN slices conduct in parallel (ring-independent, low rate). POST is off in this mode |
| `POST_POL` | in | `wiredtx.config.post_polarity` | 0 de-emphasis, 1 same sign (three-level) |
| `EN_MAIN`, `EN_POST` | in | `tx_interlock.EN_MAIN`, `.EN_POST` | the block gates both with its own ring-run detector: a stopped or partly stopped ring switches the banks off within about 0.2 us; no `tx_ring_ready` term is needed for safety |
| `ISLAND_OFF` | in | `island_off[wired]` | banks off, outputs and tail biases at VSS |
| `TAP_EN` | in | USB HS transmit request | enables the CMOS tap; `EN_MAIN` must be on (the tap reads `MAIN_P/N`), MAIN / POST codes 0 |
| `IBIAS` | in | 10 uA sourced, bank output enable = `EN_MAIN | EN_POST | TAP_EN` | |
| `MAIN_CODE0..7`, `POST_CODE0..7` | in | `wiredtx.config.current_code`, `.postcursor_code` | tail DACs as in `pt_wiredtx` |
| `TR k_b` (k 0..7, b 0..3) | in | NEW field `wtx.phase_trim[31:0]` (4 bits per phase, reset 0) | static; delay of phase k, about 13 ps per code at ss, 8 ps at ff. Set by the slot-width calibration (section 6) |
| `MAIN_P/N`, `POST_P/N` | out | pad `MAIN_P/N`, `POST_P/N` by name, shortest possible | logic 1 = `MAIN_N` high = `V(PAD_P) > V(PAD_N)` |
| `MAIN_BIAS`, `POST_BIAS` | out | pad `MAIN_BIAS`, `POST_BIAS` | as `pt_wiredtx` |
| `TAP_P`, `TAP_N` | out | `pt_usb_txdrv.CMD_P`, `CMD_N` | CMOS levels; `TAP_P` follows `MAIN_P` (low for logic 1), both low when `TAP_EN` = 0 |
| `TX_RUN` | out | wired iso clamp -> status bit | 1 = all eight conduction windows are toggling (ring-run detector) |
| `WTX_EXT_DATA` | out | wired iso clamp -> `wire_analog_status[12]` | `DX AND WTX_EXT` |
| `ATB_NBIAS`, `ATB_PBIAS` | out | ATB leaves | bias diode, MAIN DAC PMOS gate |
| `ATB_AVGP`, `ATB_AVGN` | out | two ATB sense leaves (high impedance, 100 kohm in series inside the block) | DC average of `MAIN_P` / `MAIN_N` for the phase-trim calibration |

Lower line rates: the digital repeats every line bit n times in the 40-bit word (n in 1, 2, 4, 5, 8, 10, 20, 40 so that
a word holds whole line bits), core rate = 8 x ring = n x line rate, ring 300-405 MHz. No `MODE_H` / `MODE_F`.
The postcursor is one CORE bit late.

## 3. `pt_wiredtx` (legacy; published, stays in the library until retirement)

Quarter-rate core, line <= 2.5 Gb/s.

```
 ring phases WTX_PH0/90/180/270 --> four core phases C0..C3, 1 UI apart
 D0..D39 (D0 first) --> 40 -> 20 word mux --> core wtx_serq4c: 4 x 5-bit parallel-load TSPC shift registers on C2,
                        per-stream retiming hops --> F0..F3 --> 4:1 window muxes (window k = C(k) & C(k-1)):
                        main Y / YB, postcursor DP / DPB (main delayed one line bit)
 DX (pt_diff_clk_rx on WTX_EXT_P/N) --> one-hot select core / EXT (break-before-make)
        --> CMD_MAIN_P/N = data & EN_MAIN, CMD_POST_P/N = post & EN_POST --> pads' gate drivers --> pad switches
 IBIAS (10 uA) --> two 8-bit PMOS DACs --> MAIN_BIAS / POST_BIAS (pad tail gates, ratio 16, LSB about 83 uA)
```

* Rates: quarter rate, 4 bits per ring cycle; lower line rates by bit repetition x2 / x4 in the digital
  (`MODE_H`, `MODE_F` only place the postcursor one line bit late). `WORD_CLK40` = core rate / 40.
* Each mux window closes on the falling edge of the previous phase, so the core is sensitive to the ring's phase
  duty cycle (0.57-0.58 at ss, 625 MHz): the cause of the ss failure with the real ring.
* Polarity: logical 1 = `CMD_MAIN_N` high = `V(PAD_P) > V(PAD_N)`. `POST_POL` 0 = de-emphasis, 1 = same sign (MLT-3).
* Tail DACs: MAIN code 109 = 9.05 mA (reset), 255 = 21 mA.
* `pt_wtx_hsbias`: 10 uA reference, eight binary PMOS sources into an NMOS triode load; `EN` = 0 pulls `HS_PBIAS`
  to VDD, no static current; about 2.3 mV per code at tt, +/- 20 % over PVT.
* All inputs are MOS gates on the wired rail (no current from a live core-domain driver into an unpowered island).

### Pins

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
| `CMD_MAIN_P`, `CMD_MAIN_N`, `CMD_POST_P`, `CMD_POST_N` | out | one `steer_*` buffer each (`IN`), buffer `OUT` -> pad `MAIN_P`, `MAIN_N`, `POST_P`, `POST_N`. With the pre-driver: `predrv_main.INP/INN`, `predrv_post.INP/INN` | never straight to the pad gates (about 1 kohm source into 0.5-0.9 pF). MAIN: logic 1 on the line = `CMD_MAIN_N` high = `V(PAD_P) > V(PAD_N)` (the steering buffer is non-inverting; `MAIN_N` sinks `PAD_N`). POST with `POST_POL` = 0 is the opposite sense, one line bit later (`CMD_POST_P` high for the delayed 1). Routes <= 100 fF, P/N matched. `pt_usb_txdrv.CMD_P/N` also hang on `CMD_MAIN_P/N` (about 10 fF per leg, cell placed beside these outputs; section 4, row USB-D5); the effect of that tap on the 2.5 Gb/s CMD eye has not been run |
| `MAIN_BIAS`, `POST_BIAS` | out | pad `MAIN_BIAS`, `POST_BIAS` | gate-voltage mirror, ratio 16 (diode 2 x 20/1, pad tail 32 x 20/1): keep the two blocks adjacent, VSS returns joined at the pad |
| `WTX_EXT_DATA` | out | wired iso clamp -> `wire_analog_status[12]` | `DX AND WTX_EXT` (toggles only in fallback mode), observation |
| `ATB_NBIAS`, `ATB_PBIAS` | out | ATB leaves (node 26 `wiredtx_bias`; second leaf for PBIAS) | NBIAS = reference diode, PBIAS = PMOS gate of the MAIN DAC only |

Not on the block (digital signals without an analog consumer, see WT25 / WT30): `ct_ser_run`, `ct_word_load`,
`ct_bit_phase`, `ct_qualified`, `wire_tx_request` (tie 1), `wire_tx_valid`, `wire_idle` (see "Electrical idle" below).

### TX ring and its regulator

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

### Pad, drivers of the pad gates, interlock, termination

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
| pad `TERM_VCM` | `tx_term_buffer.OUT` | 1.65 V with the termination on (wired TX benches: ideal source, 2 ohm). **TERM_VCM >= 1.0 V whenever the island is on; `tx_term_buffer` enabled by `island_on[wired]`, the switch bank still gated by `EN_TERM`** (WT51). Wired TX has no TERM_VCM-at-VSS mode (island off: 0 V). The pad netlist has `X235 TERM_VCM VSS VSS ppolyf_u_1k` 2 x 2 um (`physical.spice:255`), which reads as about 1 kohm to VSS = about 1.65 mA of static load on the buffer: pads to confirm |
| pad `ATB_ESD_RAIL` | ATB leaf or 1 Mohm to VSS | |
| `tx_term_buffer.REF`, `.BIAS`, `.ENABLE` | REF = 1.65 V source and bias branch: pads to state; ENABLE = `island_on[wired]` (WT51) | no source is bound in any netlist (mode-walk section 1) |
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

### Electrical idle, repetition, request (MW-35)

* The published block has NO idle input. With `EN_MAIN` = `EN_POST` = 0 both legs are off and the lines sit at
  `TERM_VCM` (differential 0, common mode steps up by I x 25 ohm, 0.2-0.5 V; the enables go through the interlock
  and the bias switch; their settling time has not been measured). That is a power-down, not a protocol idle: SATA OOB (106.7 ns bursts) and
  PCIe electrical idle are NOT supported today. `pt_wiredtx8` has it: pin `IDLE` on the CMD stage (both switch gates driven to
  the same level, tail current kept, differential 0 with unchanged common mode, entry / exit within one word),
  driven by `digital.wire_idle` through the wired domain. Row WT30. On `pt_wiredtx` tie nothing to `wire_idle`.
* Bit repetition x2 / x4 is the digital's (WT19); `rate_mode` selects it and drives `MODE_H/MODE_F`.
* `wire_tx_request`: no analog source, tie high (WT25(6)).

## 4. USB 2.0 data path

Demands on other owners are rows USB-D1.. .

| instance | cell | owner | state |
|---|---|---|---|
| `pad_usb` | `pad_wirepad` (top subckt `tx_protected_pad`), `analog/pads/generated/stress-safe-families/wired-receive-usb/` | pads | published (PD47 / PD48c) |
| `usb_txdrv` | `pt_usb_txdrv`, `analog/wired_tx/usbdrv.py`, `generated/usbdrv.*` | wired TX (USB) | published, see "State of `pt_usb_txdrv`" below |
| `hsbias` | `pt_wtx_hsbias`, `analog/wired_tx/hsbias.spice` | wired TX | published; `IBIAS` has no source (USB-D7) |
| `wiredtx` | `pt_wiredtx` | wired TX | published; its `CMD_MAIN_P/N` are the HS serial data |
| `rxselect`, `slicer`, `detect`, `termination`, `rxlevel`, `wmon_sel` | wired RX | wired RX | published; consumers missing (USB-D4, USB-D5) |
| USB logic in `pt_digital_macro` | - | digital | **does not exist** (USB-D1, USB-D2) |

Recorded decision used here (`spec/block-diagram.md:33`, `spec/parallel-datapath-candidate.md:23-26`,
`spec/streaming-transport-v2.md:191-206`): the FPGA owns packets (SIE, NRZI, bit stuffing, CRC); the die does the
timed physical actions (serialization, burst capture, turnaround, line drive). So the die needs no SIE, but
it does need the signals below between the digital macro and the analog cells.

### `pt_usb_txdrv` pins

Supply `VDD` = `RAIL_wired` (VDD_WIRED_SW, 3.3 V), `VSS`. Every input is a MOS gate. All outputs are
active high and are low when not enabled.

| pin | dir | connect to | notes |
|---|---|---|---|
| `CMD_P`, `CMD_N` | in | `wiredtx.CMD_MAIN_P`, `wiredtx.CMD_MAIN_N` (nets `TX_MAIN_P/N`) | HS serial data, x4 bit repetition (MODE_F), 2.083 ns bits. `CMD_P` = 1 drives D+ (J). Tap load 10 fF per leg (extracted); the cell must sit within 100 um of the `pt_wiredtx` CMD outputs (the long wires are this cell's outputs, not the CMD nets) |
| `HS_EN` | in | digital, static | `usbdrive.select.branch == hs` AND `usbhs.config.tx_enable` |
| `HS_DRV` | in | digital, timed | 1 while an HS packet is driven; 0 = HS idle (both switches off, line held at 0 V by the terminations). Word-granular is enough (row USB-D1) |
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

### `pad_usb` pins not driven by `pt_usb_txdrv`

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

### Modes (register / signal settings)

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

### State of `pt_usb_txdrv`

Strength-selectable HS gate driver, 20 pF HS_PBIAS bypass, break-before-make with direct interlock and off-delay. 208 devices, 116.48 x 270.06 um = 31,457 um2, pins on the top edge.
Magic DRC 0, Netgen LVS unique, KLayout DRC 0, KLayout precheck (main + antenna) clean
(`generated/usbdrv-layout.json`, `usbdrv-lvs.txt`, `usbdrv-drc.txt`, `usbdrv-kldrc.json`). All numbers below are
from the extracted netlist `generated/usbdrv.ext.spice` with the extracted USB pad, the extracted bias DAC and the
COB package; limits and every job result are in `generated/usbdrv-evidence.json` (bench `sim_usbdrv.py`, raw runs
`scratch/wired_tx/usbdrv/runs/`).

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

## 5. Rules and demands on other owners

Rules (details in the rows):

* **Placement (WT48, supersedes WT47's rule):** `pt_wiredtx8` R0 with origin x0 ≡ 23.75 (mod 70) um. VSS grid ties at
  block x 260.5 / 330.5 / 400.5 / 470.5; the top-edge landings at 295.5 and 505.5 sit under VDD axes and stay untied.
* **Ring phase access (WT47):** eight equal Metal5 lanes, 0.8 um wide, from the block's top edge down to Metal4
  windows at y 375.56-380.16; lane x (left edge) PH0 287.35, PH7 321.85, PH1 356.35, PH6 390.85, PH2 425.35,
  PH5 459.85, PH3 494.35, PH4 528.85. The PH routes come in from the top edge.
* **TX termination (WT51):** `pad_txpad` TERM_VCM >= 1.0 V whenever the wired island is on; `tx_term_buffer` ENABLE =
  `island_on[wired]`, the termination switch bank gated by `EN_TERM`. `pad_usb`'s TERM_VCM is a different net and is
  at VSS in every USB mode (section 4).
* **Pad current (WT52):** `MAIN_CODE + POST_CODE <= 255` (MAIN + POST <= 21 mA total) in every mode except
  100BASE-TX; per-leg average <= 10.5 mA; static one-leg current <= 15.75 mA (MAIN code <= 189, POST off) in
  `WTX_EXT` and every non-DC-balanced mode; idle MAIN/2 per leg. Digital enforces the code sum in the mode validator.
* **100BASE-TX exception (WT52-c, WT53-c; final numbers pending):** MLT-3 with MAIN + POST summed at the same sign,
  codes up to 510 in total, held leg current up to about 38-42 mA. The amplitude gap closes with no pad change:
  the pad's CASCODE pins raised to about 4.2 V in 100BASE-TX only (corner-tracking replica + pump on wired TX's
  side, bit `wtx.cascode_boost`, reset 0) and a carrier with 1:0.9 chip:line magnetics, rescaled B39 network and a
  centre tap <= 3.6 V.

| Owner | Demand |
| --- | --- |
| digital | SER_EN equation, `wire_tx_clk` = WORD_CLK40, `wire_tx_request` tie, `tx_ring_ready`, binding of the existing `ring_l.config.enable/modulus/band` and `wiredtx.config.post_polarity`, NEW `wtx.predrv_trim`, the `REQ_MAIN` combiner, decode of `rate_mode` -> MODE pins, repetition x2 / x4, interlock requests (`pt_tx_pad_sequence`), SDC including clamp + route |
| timing | PH7 (and odd-phase) skew of `ct_phbuf8` in `pt_pll_ring_core`, duty cycle at ss (WT29); reference divider or reference list; `pt_diff_clk_rx` data rate (TIM-08) |
| pads | 0.6x MAIN/POST switch resize + TMDS branch removal in one re-layout; TX termination trim (WT24); sources of `tx_term_buffer.REF/BIAS`, `DETECT_PBIAS` |
| chip-top | bindings above; delete `netlist.py` TMDS rules; instance `pll_tx`, `pll_vreg`, the four steering buffers, interlock, termination buffer; iso clamps on WORD_CLK40, WORD_CLK, WTX_EXT_DATA |
| board | one reference frequency per rate family (WT26(5)) |

## 6. Evidence

### `pt_wiredtx8` (limits in `scratch/wired_tx/s13/LIMITS.md`, declared before the runs)

Every real-chain number so far uses ring=layout-11Nov (the extracted `pt_pll_ring_core` as laid out; the committed
ring cell differs, row WT38) and pad=C (capacitance-only pad extraction) unless a row says otherwise.

* **Cause of the 3.125 Gb/s failure at the pessimistic slow corner:** in `wtx_ser8d` the first retiming hop of streams
  0, 5, 6, 7 was clocked by phase 4 and sampled the stream-register outputs 55-110 ps after they changed (register
  clock buffer 1.65 ns + register clock-to-output 0.84 ns against 4 slots + 1.30 ns of hop-clock delay): it needs a slot
  of about 335 ps, between the passing 370 ps and the failing 320 ps. The hop plan is replaced (`ser8d_macro.HOPS`).
  Real chain with the rebuilt, extracted `wtx_ser8d` and the SCHEMATIC revision-3 mux, ss pessimistic 3.15 V, pessimistic
  ring, untrimmed phases: 0 errors / 360 bits, eye 0.122 V / 0.34 UI: the errors are gone, the eye limit
  is not met without trim (`scratch/wired_tx/s13/resultsC/c1_3125_ssp.json`).
* **Extracted revision-3 mux alone** (ideal phases, ss pessimistic, 3.125 Gb/s, pad=C, 216 bits): 0 errors, 0.194 V with
  equal trim codes (limit 0.200: fail by 6 mV). The layout has a systematic 15 ps skew on one
  slice edge, which the calibration below removes (codes [1,0,0,0,0,0,0,0], residual +-3.5 ps): with those codes
  0 errors, 0.211 V / 0.64 UI (passes the screening limit; `scratch/wired_tx/s13/q_x.log`, `x3_cal_ssp`).
* **Pad with metal resistance** (pads' models `scratch/pads-core/txr/models`, mux level, extracted revision-2 mux, ideal
  phases; `scratch/wired_tx/s13/padr/padr.log`), eye in V, pad=C / pad=RC-typ / pad=RC-high: ss 2.7 Gb/s 0.482 / 0.264 / -;
  ss 3.125 0.367 / 0.203 / 4 errors; ss 3.24 0.331 / 0.186 / 10 errors; tt 3.125 0.483 / 0.210 / 0.082.
  The eye roughly halves at typical metal; every pad=C pass is optimistic. The requirement sweep for the reworked pad
  (series resistance, termination, capacitance) was queued behind this matrix (`padr.py B`).
* **Stopped-ring interlock** (`wtx_mux8` run detector): schematic, both banks on, ring stopped in state 11110000:
  supply current 42.9 mA -> 0.0 mA within 203 ns. Detector alone: runs at ff 0 C 3.63 V 240 MHz and ss 85 C 2.97 V
  420 MHz, any single stuck phase gives RUN = 0. Extracted mux: RUN rises 13-22 ns after start at ss pessimistic
  405 MHz, ff 85 C 3.63 V 240 MHz, ss 85 C 2.97 V 405 MHz. Not run: stop / stuck / mid-level / supply-ramp rows on the
  extracted netlist.
* **Phase trim:** 4 bits per phase; schematic 14.4 ps per code and 215 ps range at ss pessimistic, 8.3 ps and 162 ps at
  ff, against 2 x the worst edge span of the ring (98 ps pessimistic with the committed cell, 75 ps at ff).
  **Calibration** (`scratch/wired_tx/s13/cal.py`): the digital sends the eight one-hot words, the DC average of
  `MAIN_N - MAIN_P` on `ATB_AVGN / ATB_AVGP` measures each slot width, all eight equal is the target. Proven on known
  offsets (finds 46.6 ps, leaves +-6.7 ps). With the real ring the first results were wrong for slot 0 (measured
  during ring start-up); the corrected runs were queued and are not in hand.
* **POST bank** (extracted revision-2 mux): the "28 errors" of same-sign mode were the binary scorer on a three-level
  signal; as three levels: 0 wrong-sign samples, band separation 0.139 V at ss pessimistic and 0.193 V at ff (limit
  0.100). De-emphasis at ss pessimistic: tap ratio 0.18 at POST bias 1.0 V (eye 0.239 V, limit 0.133) and 0.35 at
  1.1 V (0.278 V, limit 0.100); at ff the same biases give 0.46 and 0.67, so the POST code must be set per chip
  (ff 0.28 at 0.9 V: 0.427 V). The 0.20 / 0.33 targets were not re-run at ff / tt bias values. POST costs 20-24 mA.
* **Fallback (EXT):** with the ring running, 1.6 Gb/s passes (0.50 V ss pessimistic, 0.69 V ff, schematic). With the
  ring stopped the all-slices-parallel path passes 0.5 Gb/s (0.87 V) and FAILS 1.6 Gb/s (16 errors / 205).
* **Idle:** with an ideal 1.9 V tail bias neither flavour meets the 100 mV common-mode limit (both gates high:
  -0.20 V; both legs on: +0.34 V); not yet measured with the block's own DAC.
* **Current:** 53 mA for the block at ss pessimistic 3.125 Gb/s, MAIN only (real chain, schematic mux);
  the mux alone 24-26 mA MAIN only, 44-52 mA with POST. The wired_tx island switch is rated 40 mA (row WT40).

Not done: the rate x corner x supply table on the final netlists (2.5, 3.0, 3.24 pessimistic, oversampled rates, sf /
fs, pessimistic ring with calibrated codes), R+C simulations, supply-impedance and Monte Carlo rows (benches exist:
`chain13.py` `supply=`, `m9.py` `mc_seed=`), the CMOS tap and idle in the real chain, the independent review of
the `pt_wiredtx8` layouts.

### `pt_wiredtx` (regenerated by `evidence.py`)

<!-- RESULTS:BEGIN (generated by evidence.py) -->
| Run | Rate | Bits/ring cycle | Corner | Result | Detail |
| --- | --- | --- | --- | --- | --- |
| cornerq2.5_ss_32_3.15 | 2.5 Gb/s | 4 | ss 32 C 3.15 V | pass | 0 errors / 140 bits, CMD jitter 162.7 ps pp, post mism. 0 |
| cornerq2.5_ff_22_3.35 | 2.5 Gb/s | 4 | ff 22 C 3.35 V | pass | 0 errors / 141 bits, CMD jitter 112.5 ps pp, post mism. 0 |
| int_tmds_q1g485 | 1.485 Gb/s | 4 | tt 27 C 3.3 V | pass | eye 1050.2 mV / 603.7 ps, 1372.0 mVpp diff, 0 errors / 219 bits |
<!-- RESULTS:END -->

Real-neighbour evidence (source = extracted ring, load = pad chain). Single-point observations (nominal extraction, CMD pins, about 100 bits each; `generated/wiredtx-realring.json`,
benches `sim_ringsrc.py` / `sim_realring.py`, row WT29):
* ss/32/3.15 V, ring supply 2.69 V, 626 MHz (2.5 Gb/s): 11 errors / 101 bits. FAIL.
* same harness, ideal full-rail phases: 0 errors, eye 240 ps.
* tt/27/3.3 V, ring supply 2.925 V: 0 errors / 101 bits, eye 226 ps (one point; not a qualification).
Not yet run: other ring supplies (2.57 V, 2.9 V, bypass), ff / sf / fs, pessimistic values, a line-level result
through the pad-gate drivers. The 3.24 Gb/s chain results are in WT31.

### `pt_usb_txdrv`

Limits and every job result: `generated/usbdrv-evidence.json` (table in section 4).

## 7. Reproduce

```
./run_wired_tx.sh                 # all stages
./run_wired_tx.sh layout          # netlist (cells.py) + layout + DRC / LVS + GDS / KLayout
./run_wired_tx.sh sims [job...]   # extracted simulations; WTX_JOBS=n parallel (default 3)
./run_wired_tx.sh evidence        # generated/*-evidence.json and the results table
python3 usbdrv.py                 # pt_usb_txdrv netlist + layout; sim_usbdrv.py = its bench
python3 sim_realring.py block '{"corner":"ss","temp":32,"vdd":3.15,"vring":2.69,"band":1,"vctrl":1.6,"tag":"x"}'
```

Magic layout / DRC / extraction and Netgen LVS run in `svalbard/librelane-gf180-canary:2026.08`; GDS export, KLayout
DRC and ngspice 43 in the pinned `hpretl/iic-osic-tools` image; decks that contain a pad use the pads family's patched
ngspice 47 (`scratch/pad-ngspice47`). Containers run with `--network none`; raw output goes to `scratch/wired_tx/`.

| File | Role |
| --- | --- |
| `cells.py` | transistor-level cells; writes `wiredtx.spice`, `hsbias.spice` |
| `serq4c_macro.py`, `serq4_macro.py` | hand-placed core macro of the published block |
| `layoutgen.py` | row placement and routing of the block around the macro |
| `usbdrv.py`, `sim_usbdrv.py` | USB pre-driver generator and bench |
| `sim_wiredtx.py`, `sim_core.py`, `sim_integration.py`, `sim_static.py`, `sim_hsbias.py` | serializer, core, pad-integration, static / safety and HS-bias benches |
| `sim_ringsrc.py`, `sim_realring.py` | real phase source (extracted ring on its regulated supply) and benches with it |
| `run_all.py`, `evidence.py`, `run_wired_tx.sh`, `tools.py` | orchestration, evidence, docker wrappers |
| `wtx_mux8.py`, `wtx_mux8_layout.py`, `ser8d_macro.py`, `wtx8_top.py`, `wtx8_aux_layout.py`, `pt_wiredtx8_layout.py` | new block: schematics and layout generators |
| `mux8.py`, `mux8_layout.py`, `mux8_layout2.py` | laid-out mux revision 2 (superseded, kept until revision 3 publishes) |
| `serq8_macro.py`, `sim_core8.py`, `cml_ser.py`, `sim_cml.py`, `wtx_fast.py`, `cells_fastpath_wip.py` | unpublished fast-path work |

## 8. Open items

1. Published `pt_wiredtx`: 2.5 Gb/s fails at ss with the real ring (rows WT29, WT32); no fix in it. Retiring it is a
   pending decision.
2. `pt_wiredtx8`: second layout pass unfinished and the schematic ahead of the layout (section 2); nothing of the
   declared limits is closed on final netlists; no pad=RC row passes at ss above 2.7 Gb/s at mux level.
3. Area: bounding box 0.351 mm2 (first pass) against the 0.22 mm2 reserve; parts 0.147 + 0.053 + 0.008, the rest is
   seam and free area. Levers: seam to <= 40 um (-0.05 mm2), L-shaped outline that returns the area beside the mux.
4. Ring: uneven phase spacing in both ring versions (WT33, WT38).
5. `wtx_ext_rx` fails from 0.5 Gb/s (TIM-08).
6. Block-level `safe` / `observable` / `fallback` tests in `generated/wiredtx-evidence.json` are open; `tmds` and
   `wtx_ext_rx` evidence files describe an older netlist.
7. 100BASE-TX: final numbers of the cascode boost + 1:0.9 magnetics plan (WT52-c, WT53-c).
8. USB (`pt_usb_txdrv`):

0. **HS at ss with per-chip supply trim** (`scratch/wired_tx/s12/usb/usbtrim.json`, same bench, ss 32 C): 394 mV at
   3.33 V (bias code 3 of 255: at the end of the range), 3.40 V (code 34) and 3.50 V (code 78); template margins
   89 / 48-70 mV; edges 550-622 ps with strength code 2 (pass), 448-517 ps with code 3 (fail). Minimum passing supply
   at ss: 3.33 V; the ss strength rule must be code 2.
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
8. **Review:** the published netlist has not had an independent review.
