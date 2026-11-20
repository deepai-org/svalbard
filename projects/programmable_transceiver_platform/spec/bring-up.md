# Bring-up sequence (pt_rf and pt_wired)

Current state, 2026-11-20. The one place for the silicon bring-up order and its software-visible rules; every step
cites the row or register that defines it. Owner: observation / debug / bring-up. Observation paths per block:
[observation.md](observation.md). Test-board assumptions: [test-board-models.md](test-board-models.md). Reference
software: `tools/bringup/` (runs this sequence against the RTL). Register names are `spec/register-map.md` fields;
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
debug 0x2020, pll 0x0404, rf 0x0202, conv 0x1010, wired 0x0101, cumulative), record the supply-current step, read
the island's rail on ATB1 (codes 7/8/9/10/11/12; rf_tx, lod, lo and wired_cap have no tap, OBS-3), then set that
island's `core.refchain.dist_en_*` and read its trunk (14 / 22 / 29 / 35 / 56). Outputs to an island stay
isolated (0) until its switch reports pgood (register-map "Safety enforcement"); `pgood_override` only for a
diagnosed dead pgood. ATB leaves on island trunks are not gated by the island (DBG-03): never close one on an off
island with a bench force.

## 6. Speed indicator and supply-trim choice (B2, MANDATE 2)

Readout: `pt_ring_osc` (21-stage 3.3 V-device ring, debug island, no bias). Two independent paths; use both:

- **CLK_OBS (primary, needs no REF_IN):** `debug.replica.ringosc_enable` = 1, `debug.clk_obs.source` = 10,
  `divider_log2` = 2; the FPGA counts CLK_OBS against its TCXO for 1 ms. f_ring = 4 × f_CLK_OBS.
- **Frequency counter (SPI):** `debug.freq_count_a.source` = 3, window 1024, target = expected count; read
  `status.freq_count_a.count` (0xF4). **Caveat OBS-2:** the counter sources are timed at 156.25 MHz and the ring runs
  166-260 MHz; until the digital owner closes OBS-2 the SPI count is a cross-check, not the reference.

Simulated (extracted `ring_osc`, `aosc`, 27 °C; decks and logs `scratch/obs-bringup/ring/`, table
`speed_table.json`; std-cell ring `scratch/obs-bringup/scring/`, schematic cells + 3 fF/node):

| Corner | ring_osc MHz 3.15 / 3.30 / 3.50 V | fc count, 1024 window, 25 MHz ref (3.15/3.30/3.50) | same, 50 MHz ref | std-cell (5 V cells) ring MHz 3.15/3.30/3.50 | aosc MHz 3.15/3.50 |
|---|---|---|---|---|---|
| ss | 166.4 / 173.8 / 183.1 | 6816 / 7119 / 7500 | 3408 / 3559 / 3750 | 134.0 / 142.1 / 152.3 | 43.3 / 42.7 |
| tt | 202.6 / 210.5 / 220.3 | 8298 / 8622 / 9023 | 4149 / 4311 / 4512 | 188.6 / 198.2 / 210.4 | 48.0 / 47.3 |
| ff | 242.0 / 249.9 / 259.6 | 9912 / 10236 / 10633 | 4956 / 5118 / 5317 | 250.6 / 261.3 / 274.9 | 54.3 / 53.6 |
| sf / fs | 201.4-201.6 / 209.0-209.8 / 218.4-219.8 | ≈ tt | ≈ tt | not run | |

Reading: corners are 17-19 % apart at a fixed supply, temperature 22-32 °C moves the ring ~1.7 %, the ring moves
+5 % from 3.30 to 3.50 V. The ring **cannot see sf/fs** (both read as tt). It tracks 3.3 V devices; the digital
macro is built from 5 V-device cells (gf180mcu_fd_sc_mcu7t5v0), whose corner spread is larger (ss/tt 0.72 vs 0.83 at
3.30 V) and whose supply gain is larger (+7.2 % vs +5.3 % for 3.30→3.50 V at ss). A cell ring in the macro (OBS-14)
would read the digital speed directly; until it exists the trim maps the ring through the PDK corner correlation.

**Trim procedure (both chips, provisional thresholds until the blocks publish their minimum passing supplies):**
1. At 3.30 V, 22-32 °C, debug island on, measure f_ring (CLK_OBS path). S = f_ring / 210.5 MHz.
2. S < 0.91 (slow; ss reads 0.83): set the regulator to **3.50 V** (B2: setpoint + 1 % + ripple + overshoot ≤ 3.63 V;
   [test-board-models.md](test-board-models.md) section 5 shows 3.57 V worst). 0.91 ≤ S ≤ 1.09: stay at 3.30 V.
   S > 1.09 (fast; ff reads 1.19): set **3.20 V** (stays in the 3.15-3.35 window with the 1 % tolerance).
3. Re-measure at the new setpoint; expected ss 183 MHz at 3.50 V. Record S, setpoint and both readings in the board
   EEPROM with `debug.calibration.tag`.
4. One setpoint serves all modes of the die (MANDATE 2). A block whose minimum passing supply at the die's corner is
   above the setpoint is a block miss, not a trim choice.

## 7. Host link (HL-*, HL-B*)

1. Clock: bring-up uses **host_follow** (no REF_IN dependency): `clockmux.config.ring_ref` = h2d, `ring_c.config.line_pll`
   = 1, `ring_c.config.modulus` = N4, `clockmux.config.hf_prescale` = D4, `debug.clk_select.host_clk` = 5 (host_follow)
   (LO-INTEGRATION 5, register-map). The FPGA runs `H2D_CLK` free (monitor `require_input_clock`). Alternative:
   `host_clk` = internal_pll from the TX ring on REF_IN (`ring_l.config.*`, `host_prescale`). Check: CLK_OBS source
   13 (host word clock) and DBG_OBS 48 (CDR ring lock); `pllvreg.config.*_bypass` stays 1 (reset) for bring-up.
2. Rate: `debug.host_link.rate` = div4 (78.125 Mb/s/pin) first (HL-B6); reset value is full rate, so set it before
   `hostio.controls.d2h_enable` = 1. `slew` = 1 (slow, reset), `d2h_stagger` = 1, `drive` reset.
3. Training: each link start sends the 8-word prefix `3A5 05A 2D3 12C 369 096 21E 1E1` once (fpga-connection-plan 1);
   the FPGA trains per-bit delay and per-lane bitslip (HL-B5, HL-TRAIN); one SPI restart per tap step (FPGA-1).
   Verify H2D with the pattern checker (`debug.pattern.check_*`, `status.pattern.errors` 0xF1 = 0) and D2H with a
   PRBS from the pattern generator.
4. Raise the rate: div2 (slow slew allowed), then full rate **only with fast slew and stagger** (HL-RATE, HL-03,
   PKG-08: unstaggered fast slew 486 mV bounce > 300 mV HL-SSO).
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

## Open items that change this sequence

OBS-2 (counter timing at ring speed), OBS-6 (per-chip ATB legality), OBS-14 (digital-speed ring), DBG-03 (ATB gating),
PWR-13 (brownout and slow-corner ramps not run), HL-03 / PKG-08 (full-rate SSO on the real ground bonds, section 7 of
[test-board-models.md](test-board-models.md)).
