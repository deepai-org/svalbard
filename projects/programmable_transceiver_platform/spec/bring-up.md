# Bring-up sequence (pt_rf and pt_wired)

Current state, 2026-11-20. The one place for the silicon bring-up order and its software-visible rules; every step
cites the row or register that defines it. Owner: observation / debug / bring-up. Observation paths per block:
[observation.md](observation.md). Test-board assumptions: [test-board-models.md](test-board-models.md). Reference
software: `tools/bringup/` (runs sections 1-7 and one mode per chip against the RTL). Register names are `spec/register-map.md` fields;
the per-chip view (D4) means a field of the other chip reads 0 and is not stored.

Steps 0-7 are the "no dead chip" path (MANDATE 1): they need only supplies, `RESET_N`, SPI, `REF_IN` and the
observation pins, and they must work with every ambitious block dead.

## 0. Board state before power (both chips)

- Supply from the per-die regulator at **3.30 V** (B2), slew ≤ 0.3 V/µs, soft start, no hot-plug (B52).
- `RESET_N` low (B1 supervisor wire-ANDed with an FPGA GPIO, B49) from before the ramp until the supply has been in
  window ≥ 1 ms (B49, B53(2)), on every power-up, strap fitted or not.
- SPI idle levels by board resistors: `CS_N` high, `SCLK` low, `MOSI` low; no SCLK edge while `CS_N` is high (B50).
- No partner drives a custom signal pad above 1 V before the supply is valid: FPGA host pins tristated (B6 bus
  switch on the 11 D2H lines and `MISO`), REF_IN oscillator, external LO, link partners, ATB force, BB/WTX_EXT
  injection all gated on power-good (B26, B53, B7). If the supply may have been back-fed, discharge below 0.5 V
  first (B53(3)).
- `POR_BYPASS` jumper not fitted (B51).

## 1. Power-up and reset

1. Ramp the supply (B52). Record the supply current with `RESET_N` low (tapeout-plan order).
2. Release `RESET_N` with `CS_N` high and SCLK low (register-map "Commit, reset and CDC").
3. Read `RESET_STATUS` 0x0D first: b0 = 1 (POR seen), b2 = strap level (0 expected), b4:2 = {POR masked, key
   override, strap} (B51). Write 0x0003 to clear b1:0, pulse `RESET_N`, read again: b1 alone = a RESET_N-only reset.
   b0 stuck at 1 with the strap = POR still asserted.
4. **POR does not release** (no SPI response, `RESET_STATUS` unreadable): rescue path 1 = fit the strap and obey B49;
   path 2 (no pad) = the SPI key sequence of `rtl/pt_por_path.sv` "RESCUE PROCEDURE" bit-banged at ≥ 1 µs per pin
   change (B51). Both need the host to pulse `RESET_N`.

## 2. SPI first contact and chip identity

SPI mode 0, 32 clocks per transaction, ≤ 1 MHz at bring-up, ≤ 5 MHz after (B50, DG8-4).

| Read | Expect | Meaning of a miss |
|---|---|---|
| 0x00 ID | 0x5356 | no SPI: check B50 levels, MISO bus switch, reset |
| 0x08 ABI_VERSION | 0x0003 | software/RTL mismatch |
| 0x09 MAP_HASH | `MAP_HASH` of the `rtl/gen/pt_regmap.py` the software was built from (DG8-7) | wrong register map |
| 0xFE `status.chip.id` | 1 = pt_rf, 2 = pt_wired | wrong die on this carrier: stop |
| 0x0A ISLAND_STATUS | 0x0000 | pgood with island off = back-drive signature (register-map 0x0A): find the driven pad |
| 0x05 CONFIG_ERROR, 0x0B FAULT_STATUS | 0 | |

## 3. Always-on observation (no island, no bias)

1. `core.aosc.enable` = 1 (0x5E, direct). `debug.dbg_obs.sel0` = 35 (aosc_div): DBG_OBS0 toggles. This is the
   first proof that the core rail, the macro and a clock work.
2. `refinput.state` = active (0x80; pt_rf: `rfpll.config.lo_mode` not 1/3, ctl_ports `c_rx_ref_en`) with the board
   REF_IN oscillator on (B23(3): 25 MHz class on pt_wired; pt_rf uses the LO reference, 50.0-51.74 MHz,
   LO-INTEGRATION 4.2). DBG_OBS0 sel 11 (ref_present) = 1.
3. Frequency counter a: source 5 (aosc), window 1 (1024), commit; read 0xF4 twice ≥ 2 windows apart. Count =
   f_aosc / f_ref × 1024 (aosc 42.7-54.3 MHz over corners, table in section 6). This proves `ref_clk` and the counter.

## 4. Bias (bandgap, trims) — B54

1. `core.biasgen.ena` = 1 and `core.refchain.bgap_ena` = 1, commit.
2. Wait ≥ 100 µs **and** clock ≥ 256 SCLK of SPI traffic (nine 32-clock ID reads) before relying on any bias: the
   macro's bandgap interlock counts SCLK, which runs only in transfers (B54, CB8-9). Until then `ref_sel_vbg` and
   every `dist_en` read back as written but are held 0. DBG_OBS sel 12 (bandgap_ok) shows it.
3. `ref_sel_vbg` = 1, `ref_sel_coarse` = 1 (commit rule 28: fine needs coarse).
4. Per-die trims (`analog/core_support/README.md` "Per-die trims"): ATB1 code 55 VBG → `bgap_trim` closest to
   1.200 V; IDAC1 on ATB1 code 57 into an SMU at ~1 V → `idac2_source` = round(100 µA / I_meas).
5. Walk ATB1 codes of this chip ([observation.md](observation.md) code table): 1, 2, 3, 5, 13, 57. Never select a
   code that has no leaf on this chip (bus floats; OBS-6). ATB0 force only on a powered chip, ≤ 1 mA source (B7),
   and only with the force preconditions (commit rules 29-35).

## 5. Islands — one at a time, record each current step

Enable groups (power-delivery.md section 2): `debug.island_power` bit 5 debug, 2 pll, then pt_rf: 1 rf (rf_rx, rf_tx,
lod, lo), 4 conv; pt_wired: 0 wired (wired_rx, wired_cap, wired_tx a+b). Order: **debug, pll, then the payload
groups**. For each: write the bit, commit, wait 20 µs, read 0x0A (effective-on b5:0 and pgood b13:8 must both set:
debug 0x2020, pll 0x0404, rf 0x0202, conv 0x1010, wired 0x0101, cumulative) **and every switch of the group in
`status.health.switch_pg` (0xFF: rf = b0-b3 rf_rx/rf_tx/lod/lo, wired = b4-b6, pll b7, conv b8, debug b9; OBS-IMPL-4: a dead
switch inside a group shows here although the group pgood is an AND)**, record the supply-current step, read
the island's rail on ATB1 (codes 7/8/9/10/11/12; rf_tx, lod, lo and wired_cap have no tap yet, OBS-3), then set that
island's `core.refchain.dist_en_*` and read its trunk (14 / 22 / 29 / 35 / 56). ATB codes with no leaf on the chip
are rejected at write (CONFIG_ERROR b0, OBS-IMPL-3); ATB0 trunk forces close only with their island on (OBS-IMPL-5).
Outputs to an island stay
isolated (0) until its switch reports pgood (register-map "Safety enforcement"); `pgood_override` only for a
diagnosed dead pgood.

## 6. Speed indicator and supply-trim choice (B2, MANDATE 2)

Readout: `pt_ring_osc` (21-stage 3.3 V-device ring, debug island, no bias). Two independent paths; use both:

- **CLK_OBS (primary, needs no REF_IN):** `debug.replica.ringosc_enable` = 1, `debug.clk_obs.source` = 10,
  `divider_log2` = 2; the FPGA counts CLK_OBS against its TCXO for 1 ms. f_ring = 4 × f_CLK_OBS.
- **Frequency counter (SPI):** `debug.freq_count_a.source` = 3, window 1024; read `status.freq_count_a.count` (0xF4).
  **Source 3 is counted through a /2 flop (OBS-IMPL-1, timed at 278 MHz): f_ring = 2 × count × f_ref / window.**
- **Digital-cell ring (OBS-IMPL-2):** `debug.replica.dig_ring_enable` = 1 (0x4E b5), counter source 7, also /2:
  f_dig = 2 × count × f_ref / window. `pt_dig_ring` = nand2 + 40 inv_1 of gf180mcu_fd_sc_mcu7t5v0 (the macro's cells),
  core supply. Switch it off after the reading.

Simulated (extracted `ring_osc`, `aosc`, 27 °C; decks and logs `scratch/obs-bringup/ring/`, table
`speed_table.json`; std-cell ring `scratch/obs-bringup/scring/`, schematic cells + 3 fF/node):

| Corner | ring_osc MHz 3.15 / 3.30 / 3.50 V | source 3 count (= edges/2), 1024 window, 25 MHz ref | same, 50 MHz ref | dig_ring MHz 3.15 / 3.30 / 3.50 (estimate) | source 7 count, 25 / 50 MHz ref, 3.30 V | aosc MHz 3.15/3.50 |
|---|---|---|---|---|---|---|
| ss | 166.4 / 173.8 / 183.1 | 3408 / 3560 / 3750 | 1704 / 1780 / 1875 | 68.6 / 72.8 / 78.0 | 1491 / 745 | 43.3 / 42.7 |
| tt | 202.6 / 210.5 / 220.3 | 4149 / 4311 / 4512 | 2075 / 2155 / 2256 | 96.6 / 101.5 / 107.8 | 2079 / 1039 | 48.0 / 47.3 |
| ff | 242.0 / 249.9 / 259.6 | 4956 / 5118 / 5317 | 2478 / 2559 / 2658 | 128.4 / 133.8 / 140.8 | 2740 / 1370 | 54.3 / 53.6 |
| sf / fs | 201.4-201.6 / 209.0-209.8 / 218.4-219.8 | ≈ tt | ≈ tt | not run | | |

dig_ring estimate = the 21-stage mcu7t5v0 schematic ring of `scratch/obs-bringup/scring/` (3 fF per node) scaled by
21/41 stages; the digital owner's Liberty estimate is 54 MHz ss / 120 MHz ff (no wire). Replace both by the routed,
extracted number after hardening (digital, OBS-IMPL-2). The RTL model of the cell runs at 76.9 MHz (HALF_NS 6.5),
so a simulated die reads as "slow digital".

Reading: corners are 17-19 % apart at a fixed supply, temperature 22-32 °C moves the ring ~1.7 %, the ring moves
+5 % from 3.30 to 3.50 V. The ring **cannot see sf/fs** (both read as tt). It tracks 3.3 V devices; the digital
macro is built from 5 V-device cells (gf180mcu_fd_sc_mcu7t5v0), whose corner spread is larger (ss/tt 0.72 vs 0.83 at
3.30 V) and whose supply gain is larger (+7.2 % vs +5.3 % for 3.30→3.50 V at ss). A cell ring in the macro (OBS-14)
would read the digital speed directly; until it exists the trim maps the ring through the PDK corner correlation.

**Trim procedure (both chips; thresholds accepted provisionally by the coordinator until the blocks publish their
minimum passing supplies):**
1. At 3.30 V, 22-32 °C, debug island on, measure f_ring (CLK_OBS path, counter cross-check) and f_dig (counter source
   7). S = f_ring / 210.5 MHz (3.3 V devices: analog, CML, rings); S_dig = f_dig / f_dig(tt, 3.30 V) (5 V-device cells:
   the digital macro).
2. **Slow** if S < 0.91 (ss reads 0.83) **or** S_dig < 0.86 (ss reads 0.72): set the regulator to **3.50 V** (B2:
   setpoint + 1 % + ripple + overshoot ≤ 3.63 V; [test-board-models.md](test-board-models.md) section 4: 3.563 V worst).
   **Fast** only if S > 1.09 (ff 1.19) **and** S_dig > 1.16 (ff 1.32): set **3.20 V**. Otherwise stay at 3.30 V. The
   two rings disagreeing by more than one class (one slow, one fast) is a finding: record both and report it.
3. Re-measure at the new setpoint; expected ss 183 MHz (ring_osc) and ~78 MHz (dig_ring) at 3.50 V. Record S,
   S_dig, setpoint and the readings in the board
   EEPROM with `debug.calibration.tag`.
4. One setpoint serves all modes of the die (MANDATE 2). A block whose minimum passing supply at the die's corner is
   above the setpoint is a block miss, not a trim choice.

## 7. Host link (HL-*, HL-B*)

1. Clock (baseline host follow on the TX ring, D-HF; `integration/chips/sim/tb_top_modes.sv` section 2):
   `clockmux.config.ring_ref` = h2d (3), `ring_l.config.modulus` = 4 (code 2), `ring_l.config.enable` = 1,
   `clockmux.config.host_prescale` = /4 (code 2), `debug.clk_select.host_clk` = internal_pll (1). The ring runs at
   4 × f(H2D_CLK) and the word clock equals f(H2D_CLK); the FPGA keeps `H2D_CLK` free-running (monitor
   `require_input_clock`). Needs no REF_IN. Check: CLK_OBS source 13 (host word clock), DBG_OBS 10 (TX ring lock);
   `pllvreg.config.*_bypass` stays 1 (reset) for bring-up. Alternative: the CDR ring (`ring_c.config.line_pll` = 1,
   `hf_prescale`, `host_clk` = host_follow 5).
2. Rate: `debug.host_link.rate` = div4 (78.125 Mb/s/pin) first (HL-B6); reset value is full rate, so set it before
   `hostio.controls.d2h_enable` = 1. `slew` = 1 (slow, reset), `d2h_stagger` = 1, `drive` reset.
3. Training: set `hostio.controls.d2h_enable` = 1 first. A **link start is the payload `ENABLE` (0x01 b0) going
   0 → 1**: the transport core leaves reset and sends the 8-word prefix `3A5 05A 2D3 12C 369 096 21E 1E1` once
   (`rtl/pt_core.sv` crst, `pt_quad_link_tx`; fpga-connection-plan 1). Toggling `d2h_enable` or the rate does not
   resend it. The FPGA trains per-bit delay and per-lane bitslip (HL-B5, HL-TRAIN): per tap step write ENABLE 0, move
   the tap, write ENABLE 1, search the capture for the prefix (FPGA-1); centre of the passing taps.
   H2D health: `status.health.h2d_overflow` / `h2d_underflow` (0xFF b10 / b11, sticky until reset, OBS-IMPL-6) must
   read 0 after training and traffic at each rate; on pt_wired also the pattern checker (`status.pattern.errors` 0xF1).
4. Raise the rate: div2 (slow slew allowed), then full rate with fast slew (HL-RATE: slow slew leaves 1.65 ns of eye
   against 1.68 ns at ss). Ground bounce on the real bond sets (OBS-15, [test-board-models.md](test-board-models.md)
   section 6) is 139-215 mV fast-edge worst case, inside the 300 mV HL-SSO limit with or without stagger; keep
   `d2h_stagger` = 1 at full rate for margin.
5. **pt_rf RF modes (DG9-7, RQ-16):** `host_link.rate` = div4 + slow slew + stagger with MODE8 or ≤ 0.72 Gb/s; 12-bit
   I/Q at 40 MS/s needs div2 + slow slew + stagger with the FPGA host word clock chosen per RF channel in 109-156.25 MHz
   so that no harmonic of the word clock (and of the core clock = word/2) falls inside the wanted channel ± its
   bandwidth (FPGA table; HL-RATE). Above 156.25 MHz is not timed. Monitor and timeout fields counted in hcore ticks
   scale with the chosen clock.

## 8. Observation readout per block

Walk [observation.md](observation.md) for the chip: ATB codes, CLK_OBS sources, DBG_OBS selects and counter sources
per block, each with its island on. Ring PLL: counter a source 1 (TX ring FBCK) locks to target; CDR ring: counter b
source 2. pt_rf LO: counter source 6 (LO_FB = f_VCO/2N) per band, LO-INTEGRATION 4.2.

## 9. Per-mode enable sequences

Each mode's register sequence is the block owner's; the generic rules are:
- Shadow writes then one commit; `CONFIG_ERROR` 0x05 and `ERROR_INFO` 0x0C after every commit.
- Break-before-make: a field never goes from one non-zero code to another in one commit (register-map rules).
- Islands first (section 5), then `dist_en`, then block states warm → active.
- pt_rf: on-chip LO = LO-INTEGRATION 4.2 (band search on counter source 6, `lo_icp` = 3); external LO = B3/B19/B31
  after power-up (B26); RX = LNA → mixers → bbfilter → ADC, calibration in register-map "Per-board calibration
  sequence" steps 2-7; TX = DAC → bbfilter tx → txmix → txsum → rfdriver with `rfdriver.mute` until the board
  network (B17) is confirmed.
- pt_wired: rings (`ring_l`, `ring_c`), then termination (`termination.config`), CTLE, slicer, capture
  (`status.wired.rx_*`); TX through the pad interlock (`txpad.config.branch`, `status.wired.tx_state`); USB per
  `analog/wired_tx/USB-INTEGRATION.md` with B11 amplitude calibration; fallback first (tapeout-plan), e.g. the
  WTX_EXT → WIRE_TX route (`debug.wtx_ext.enable`, verification/check_chip_fallback.py).
- Fault monitor (`monitor.config.*`) armed only after the requirements it watches are running; clear with
  `monitor.reset.clear_fault` 1 then 0.

## 10. Bench test plan (first silicon, per chip)

Measure in this order; stop at the first STOP. Expected values are from the evidence named; a limit is the evidence
range widened only where the evidence has no corner data (marked ±30 %, a screening limit, not a spec). All at
3.30 V, 22-32 °C, sections 0-7 board state. `tools/bringup/` automates T2-T11 (ATB through an SMU back-end).

### Both chips

| # | Measure | Expected (basis) | Pass | On fail |
|---|---|---|---|---|
| T1 | Supply current, `RESET_N` low | ≈ 4.6 mA stopped (spec/budgets/power-budget.json `stopped` 4.62 mA; 15 mW) | 1-15 mA | > 15 mA: STOP, power off (short / latch-up / back-feed, B53); < 1 mA: open supply bond or no die |
| T2 | 0x00 / 0x08 / 0x09 / 0xFE | 0x5356 / 0x0003 / map hash / 1 rf, 2 wired | exact | no answer: B50 levels, B51 rescue; wrong id: STOP (wrong die) |
| T3 | `RESET_STATUS` after power-up | b0 = 1, b2 = 0 | exact | b0 = 0: POR never fired; b0 stuck 1: POR stuck (B51) |
| T4 | `ISLAND_STATUS`, all off | 0x0000 | exact | pgood with island off = back-drive: find the driven pad (B53) |
| T5 | aosc on counter source 5 | 42.7-54.3 MHz extracted ss..ff, 3.15-3.50 V (section 6) | 40-60 MHz (design window) | REF_IN absent (DBG_OBS 11), counter, or aosc fault: use CLK_OBS 12 |
| T6 | Current step: bias enable | bandgap 87-161 µA + biasgen (core_support README) | 0.05-0.5 mA | |
| T7 | ATB1 55 VBG, untrimmed | 1.204-1.220 V (core_support evidence, tt/ss/ff) | 1.17-1.25 V | outside: bandgap / ATB path; ATB1 13 (VSS) and 5 (VDD) prove the bus |
| T8 | VBG after `bgap_trim` | 1.200 V | 1.190-1.210 V (SMU ≥ 1 GΩ) | trim range exhausted: record, continue untrimmed |
| T9 | ATB1 1 / 2 / 3 / 57 | ROOT_REF 0.92 V; VREF0 = 5/6 VBG; VCM = VDD/2; IDAC1 0.94 µA/LSB (code 10 = 9.4 µA into ~1 V) | 0.80-1.05 V; ±1.5 %; ±1 %; ±30 % | set `idac2_source` from IDAC1 (section 4) |
| T10 | Each island on, blocks off: ISLAND_STATUS, rail (ATB1 7-12), current step | pgood + effective-on bits; rail ≥ VDD − 20 mV (switch drop ≤ 19.9 mV at design current, power-budget `island_switch`) | bits exact; rail ≥ VDD − 50 mV; step < 2 mA | step > 10 mA: STOP that island (short / latch); pgood without rail: pgood logic |
| T11 | Ring oscillator (CLK_OBS 10, then counter 3 × 2) and digital ring (counter 7 × 2) | ring_osc 173.8 / 210.5 / 249.9 MHz at ss / tt / ff; dig_ring ~73 / 101 / 134 MHz (estimate) at 3.30 V | ring_osc 150-280 MHz, CLK_OBS and counter within 1 %; dig_ring 45-160 MHz | set the supply trim (section 6) |
| T12 | TX ring: counter source 1 against target; DBG_OBS 10 lock | count = target ± tolerance | locked within 1 ms | band / modulus; ATB1 30 VCTRL not at a rail |
| T12a | Per-switch power-good with each group on | `status.health.switch_pg` bits of the group set | exact | a dead switch inside an AND group: STOP that group |
| T13 | Host link, div4: training window (FPGA tap sweep); H2D health 0xFF b10/b11 = 0 | D2H budget 2.06 ns of a 3.2 ns UI at full rate (interface-requirements 3.1) | div4 ≥ 6 ns of 12.8 ns; div2 ≥ 3 ns of 6.4 ns (fpga-connection-plan); full rate ≥ 0.6 ns | stay at the slower rate; check stagger / slew |

### pt_rf

| # | Measure | Expected (basis) | Pass |
|---|---|---|---|
| R1 | Current steps per block enable (rf island) | LNA 18.9-21.4 mA (19.0 limit), rxmix 3.01-3.09 each, bbfilter 5.22-5.32 each (power_budget.py MEASURED, extracted) | ±30 % of nominal; LNA ≤ 21.4 mA |
| R2 | conv island: ADC, DAC, refbuf | ADC 5.73 / 5.72 mA, DAC 2.07 each, refbuf 0.55 mA (+1 mA delivered) | ±30 %; DBG_OBS 13 refbuf_ready = 1; ATB1 36 VREF_CONV recorded |
| R3 | Converter loopback DAC → bbfilter rx_direct → ADC (MEMORY capture) | tone at the programmed frequency | SNDR recorded; the published ADC FFT is ENOB 4.9 (MOD-04): screening pass ≥ 4 ENOB |
| R4 | On-chip LO band search, counter source 6 (LO_FB = f_VCO / 2N) | count = f_ref × 1024 / 1024 at lock for the band chosen (LO-INTEGRATION 4.2) | a band locks for 2.400-2.4835 GHz; CLK_OBS 1 = f_LO / 8 / 2^N agrees |
| R5 | RX tone at BB_I/Q taps, then ADC | gain per the rf_rx README chain rows | recorded; I/Q 90° ± 10° before trim |
| R6 | RF_TX output (spectrum analyser, B17) | per rf_tx README matched powers minus placement loss (test-board-models 3) | recorded; mute drops it > 30 dB |
| R7 | ATB1 15-21, 33, 38, 39 bias nodes | no published node values (OBS row gap) | record; flag a node at a rail (< 0.1 V or > VDD − 0.1 V) |

### pt_wired

| # | Measure | Expected (basis) | Pass |
|---|---|---|---|
| W1 | pll island: CDR ring current step | 6.85-10.2 mA (power_budget.py pll_cdr) | within |
| W2 | Wired TX: `status.wired.tx_state` = 3, ring ready; MAIN tail step | tail 9.05 mA at code 109 (wired_tx INTEGRATION) | ±30 %; eye on WIRE_TX (scope, B22) recorded per rate |
| W3 | Fallback route WTX_EXT → WIRE_TX (B12) | data through at 0.5 Gb/s (check_chip_fallback.py) | 0 errors in 10^4 bits |
| W4 | Termination by SMU on the pads (powered, term on/off, ≤ 1 mA, B7): USB_DP/DN and WIRE_RX_P/N | USB `pad_wirepad`: 40.5-49.5 Ω per leg in candidate b5, 165-255 Ω in the published cell (PC-50); WIRE_RX `pad_hspad`: per the pads README after the PAD-09 fix | USB 40-55 Ω with the b5 cell; record which cell shipped; off > 10 kΩ |
| W5 | Wired RX loopback cable TX → RX, PRBS7, `status.pattern.errors` | 0 errors at 1.25 Gb/s (wired_rx README real-neighbour rows) | 0 in 10^9 bits at 1.25 Gb/s; record 2.5 / 3.24 Gb/s |
| W6 | USB HS amplitude (B11) | 360-440 mV after `usbhs.bias.code` calibration | within |
| W7 | ATB1 23, 24, 26, 27, 28, 40 | no published node values | record; flag a node at a rail |

## Open items that change this sequence

OBS-2 / 6 / 14 / 17 / 3 (status) are implemented (OBS-IMPL-1..6, e3bfb4b2); open: OBS-3 / 4 / 5 / 7 / 11 sense leaves,
OBS-12 dead codes, the routed dig_ring frequency,
PWR-13 (brownout and slow-corner ramps not run), HL-03 / PKG-08 (full-rate SSO on the real ground bonds, section 7 of
[test-board-models.md](test-board-models.md)).
