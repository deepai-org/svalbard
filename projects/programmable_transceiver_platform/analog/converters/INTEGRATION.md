# Converter interface for chip-top (`adc_i`, `adc_q`, `dac_i`, `dac_q`, `refbuf`)

Two interfaces exist and they differ in the clock pins:

| | Published cells (`generated/`, `<block>.spice`) | Staged candidate (`scratch/converters-ap4/stage4/`, `CONV_AP4=1`) |
|---|---|---|
| Clock | differential low-swing `CLKP/CLKN` (CM 1.65 V, 0.4 V peak); the ADC acquisition window is the clock high time, shaped outside the block (6 ns at 40 MHz in the evidence) | one single-ended 3.3 V CMOS `CLK`; ADC window made on the block (`ACQ1:0`), `PH` output; DAC captures on the falling edge |
| ADC outline | 465.46 × 1241.16 µm (0.578 mm²) | 480.28 × 936.30 µm (0.450 mm²) |
| DAC outline | 674.50 × 275.93 µm (0.186 mm²) | 668.50 × 200.63 µm (0.134 mm²) |
| State | published; evidence in `generated/` | not published; Magic DRC 0, LVS unique, precheck 0/0 on the staged GDS |

`integration/top/pt_chip.conn` binds the ADCs and DACs to the **staged** pin list (masters marked `staged` in
`integration/top/masters.txt`, decision D-CONV), so sections 1 to 6 describe that contract. Section 7 gives the
published pin lists. `refbuf` is the same in both.

All pins are Metal4 at the block's north edge in the west trunk bank. `adc_q` / `dac_q` have the layouts of
`adc_i` / `dac_i`. Items marked **OPEN** are not backed by a simulation.

## 1. Clock (staged contract)

Each ADC and DAC has one clock pin `CLK`: 3.3 V CMOS, single-ended, gate-only (safe with the conv island off),
gated on the block by the block's own enable. The top does not shape or invert the clock.

| Block | `CLK` net in `pt_chip.conn` |
|---|---|
| adc_i, adc_q | `CONV_CLK_C` = `clockmux.CONV_CLK` through one `iso_clamp_x4` in the conv domain |
| dac_i, dac_q | `rf_tx_clk_out` of the digital macro (source-synchronous TX) |

### 1.1 ADC
- The acquisition window opens on the rising `CLK` edge and closes after an on-block delay (one-shot). The
  sampling instant is the end of the window.
- `ACQ1:0` (static, `adc.config.acquisition`, one value for I and Q): `0` nominal window (reset value),
  `1` short, `2` long, `3` window = `CLK` high time with sampling on the falling edge. Code 3 fits only when
  2 × T_clk − T_high covers the conversion (39.1 ns worst case): ≤ 37 MHz interleaved at ss with a 50 % clock,
  ≤ ~11 MHz single core. It is a bring-up option.
- `CLK` requirements (codes 0–2): ≤ 40 MHz; high and low time each ≥ selected window + 1 ns; rms jitter
  ≤ 20 ps (assumed bound, section 5).
- `ILEN = 1` (`adc.config.interleave`): two interleaved cores, one sample per `CLK` period. `ILEN = 0`: core A
  only, `CLK` ≤ 20 MHz.
- `PH` (output): interleave phase. `PH = 0`: the next rising edge starts an acquisition in core A; `PH = 1`: in
  core B. It changes 5–8 ns after a rising edge and is stable at the next one. With `ILEN = 0` it stays 0.
- Enable: the block gates the clock with `EN` delayed by 5–10 ns. If `EN` rises while the clock runs, the first
  acquisition can be a runt. Rule: discard the first 4 samples after `EN` rises or after the clock is started
  or re-selected. The A/B order is read from `PH`, never inferred.

### 1.2 DAC
- Captures `CODE9:0` on the falling `CLK` edge; the macro launches on the rising edge of `rf_tx_clk_out`. The
  output updates one clock period after the capturing edge.
- Setup/hold of `CODE` to the falling edge at the block pins: **OPEN**. `CLK` ≤ 80 MHz.
- Enable with `HOLD_ZERO = 1` (its reset value) and release `HOLD_ZERO` at least 2 clock periods later; if `EN`
  rises while `CLK` is high the registers can otherwise see one runt clock.

### 1.3 Duplex
ADC and DAC have separate `CLK` pins, so their rates need not be equal. An 80 MHz DAC clock with a 40 MHz ADC
clock is not benched.

## 2. Sample handshake (staged contract)

The converters produce no clocks and no request.
- Macro clocks: `rf_rx_clk` = `CONV_CLK` through a core-domain clamp, `rf_tx_clk` = `CONV_CLK`.
- ADC outputs per core: `CODE9:0`, `DONE`, `OVERLOAD` (core A) and `CODEB9:0`, `DONEB`, `OVERLOADB` (core B),
  10-bit two's complement, bit 9 = MSB. Core A goes to `rf_rx_sample[11:2]` (I) / `[23:14]` (Q), core B to
  `rf_rx_sample_b` with the same bit positions. A core's register is written when its conversion ends and holds
  until its next conversion ends.
- Capture with `ILEN = 1` (one flop stage on rising `CONV_CLK`): at every rising edge read `PH`; `PH = 0`
  registers core A's word, `PH = 1` core B's. That word is the sample acquired two edges earlier; it is stable
  from at most 45 ns after its own edge until at least 20 ns after the capturing edge (≥ 4 ns setup at ss).
  With `ILEN = 0`: register core A at every rising edge.
- `rf_rx_valid` is made inside the macro: `EN` and 4 edges counted since enable or clock start.
- `DONE` / `DONEB` are level flags (status only); nothing is clocked by them.
- The DAC has no request output: one code per `CLK` period, from `rf_tx_sample[11:2]` (I) / `[23:14]` (Q).
- `CODE*`, `CODEB*`, `DONE*`, `OVERLOAD*`, `PH`, `READY` cross from the conv island into the core through the
  macro's isolation clamps.

## 3. References and bias

| Pin | Block | Net in `pt_chip.conn` | Notes |
|---|---|---|---|
| `VREF0` | refbuf | `VREF0_MASTER` (1.0 V from core bias) | gate input, no DC load |
| `VREF` | refbuf (out), adc_i, adc_q | `VREF_CONV` | one refbuf for both ADCs (**OPEN**: benched with one ADC). ≥ 2 µm wide, star from the refbuf, away from clocks. ATB node `conv_vref`. |
| `VCM` | adc_i, adc_q | `VCM_MASTER` (VDD/2 from core bias) | **OPEN**, CNV-06: the source is a 40 kΩ divider without decoupling (section 5) |
| `IBIAS` | all five | `BIAS_adc_i/q`, `BIAS_dac_i/q`, `BIAS_refbuf`: one 10 µA leg each, sourced into the pin | NMOS diode to VSS inside. In the staged ADC nothing uses the diode; the leg stays bound so `ATB_BIAS` shows that bias arrives. |
| `ATB_BIAS` | adc_i, dac_i | `ATBN_adc_bias`, `ATBN_dac_bias` (I only; Q unconnected) | observation only |
| `VDD`, `VSS` | all | `RAIL_conv`, `VSS` | |

## 4. Pin lists (staged contract, subcircuit port order)

`pt_adc_i` / `pt_adc_q`:
`VDD VSS INP INN VCM VREF IBIAS CLK ACQ0 ACQ1 EN ILEN TEST0 TEST1 CODE0..CODE9 DONE OVERLOAD CODEB0..CODEB9 DONEB OVERLOADB ATB_BIAS PH`

`pt_dac_i` / `pt_dac_q`:
`VDD VSS OUTP OUTN IBIAS CLK EN HOLD_ZERO CODE0..CODE9 ATB_BIAS`

`pt_refbuf`: `VDD VSS VREF0 VREF IBIAS EN OVR READY`

| Pin | Dir | Type | Chip-top net |
|---|---|---|---|
| adc `INP/INN` | in | analog differential, CM 1.65 V, about ±0.9 V full scale | `ADCI_P/N`, `ADCQ_P/N` (`bbfilter_*.out_rx`) |
| adc `CLK` | in | CMOS | `CONV_CLK_C` |
| adc `ACQ0, ACQ1` | in | CMOS static | `c_adc_acq[1:0]` |
| adc `EN` | in | CMOS | `c_adc_i_en`, `c_adc_q_en` |
| adc `ILEN` | in | CMOS static | `c_adc_ilen` |
| adc `TEST0, TEST1` | in | CMOS static | `c_adc_i_test[1:0]`, `c_adc_q_test[1:0]` |
| adc `PH` | out | CMOS | `ADCI_PH`, `ADCQ_PH` |
| adc `CODE*, CODEB*, DONE*, OVERLOAD*` | out | CMOS | `ADCx_CODE`, `ADCx_CODEB`, `ADCx_DONE(B)`, `ADCx_OVL(B)` |
| dac `CODE9:0` | in | CMOS | `rf_tx_sample[11:2]` (I) / `[23:14]` (Q), two's complement |
| dac `CLK` | in | CMOS | `rf_tx_clk_out` |
| dac `EN`, `HOLD_ZERO` | in | CMOS | `c_dac_*_en`, `c_dac_*_hold_zero` |
| dac `OUTP/OUTN` | out | analog differential | `DACI_P/N`, `DACQ_P/N` |
| refbuf `EN`, `OVR`, `READY` | in, in, out | CMOS | `c_refbuf_en`, `c_refbuf_ovr`, `REFBUF_READY` |

## 5. Numbers behind the staged contract

Acquisition window: schematic one-shot, 60 fF load, 40 MHz (`scratch/converters-ap4/val/shaper19/`). Extracted
values: **OPEN**.

| `ACQ1:0` | tt 27 °C 3.3 V | ss 32 °C 3.15 V | ff 22 °C 3.35 V |
|---|---|---|---|
| 0 nominal | 5.0 ns | 6.1 ns | 4.4 ns |
| 1 short | 3.3 ns | 4.0 ns | 2.9 ns |
| 2 long | 6.3 ns | 7.6 ns | 5.4 ns |
| 3 clock high time | 12.5 ns at 40 MHz / 50 % | same | same |

- Rising `CLK` edge to window start: 0.28–0.42 ns. Conversion budget with `ILEN = 1`: 2 × T_clk − window.
- Codes 0–2: the sampling instant moves −1.6 ps per mV of `VDD_CONV_SW` (nominal window, tt). 10 mV of supply
  ripple correlated with the input gives 16 ps: SNR bound 54 dB at 19 MHz, 60 dB at 10 MHz (CNV-07).
- Clock jitter: SNR bound = −20 log10(2π f_in σ); 20 ps rms gives 58 dB at 10 MHz. The 20 ps is an assumed
  pessimistic bound for the ring-PLL / prescaler path, not a measurement. Whether the conv-domain clamp on
  `CONV_CLK` fits inside it is **OPEN** (D-CONV).
- `VCM`: the core-bias source is a 40 kΩ (Thevenin) divider with no decoupling. The ADC resets its LSB-array
  node to `VCM` in every window and, in `input_test` 1–3, samples `VCM` on the 0.44 pF top plates (τ about
  36 ns against a 5 ns window: those test levels will not settle). Every ADC bench uses an ideal 1.65 V source;
  plan for a decoupling capacitor on the `VCM` net (CNV-06).
- Extracted coupling at the staged pins: `INP`–`VCM` 73 fF, `INN`–`VCM` 79 fF, `CLK`–`PH` 78 fF.

## 6. Staged outlines and pin x positions

µm; x = 0 at the west edge of the device rows, trunk bank at x < 0
(`scratch/converters-ap4/meas/meas.json`). Pins 0.4 µm wide on a 0.7 µm pitch; `VDD`/`VSS` 2 µm, `VREF` 1 µm.

`adc_i / adc_q`: bbox x −48.20..432.08, y 0.50..936.80. Pins west to east:
`OVERLOADB`@-44.4 `OVERLOAD`@-43.7 `DONEB`@-39.5 `DONE`@-38.8 `CODEB9`@-36.7 `CODEB8`@-36.0 `CODEB7`@-35.3 `CODEB6`@-34.6 `CODEB5`@-33.9 `CODEB4`@-33.2 `CODEB3`@-32.5 `CODEB2`@-31.8 `CODEB1`@-31.1 `CODEB0`@-30.4 `CODE9`@-29.7 `CODE8`@-29.0 `CODE7`@-28.3 `CODE6`@-27.6 `CODE5`@-26.9 `CODE4`@-26.2 `CODE3`@-25.5 `CODE2`@-24.8 `CODE1`@-24.1 `CODE0`@-23.4 `PH`@-21.3 `CLK`@-20.6 `ACQ1`@-19.9 `ACQ0`@-19.2 `ILEN`@-18.5 `ATB_BIAS`@-17.5 `EN`@-16.5 `IBIAS`@-15.5 `TEST1`@-14.5 `INN`@-13.5 `VCM`@-12.5 `INP`@-11.5 `TEST0`@-10.5 `VREF`@-8.5 `VSS`@-6.0 `VDD`@-3.0

`dac_i / dac_q`: bbox x −28.50..640.00, y 0.50..201.13. Pins west to east:
`CLK`@-28.2 `CODE9`@-26.8 `CODE8`@-26.1 `CODE7`@-25.4 `CODE6`@-24.7 `CODE5`@-24.0 `CODE4`@-23.3 `CODE3`@-22.6 `CODE2`@-21.9 `CODE1`@-21.2 `CODE0`@-20.5 `HOLD_ZERO`@-19.8 `EN`@-19.1 `IBIAS`@-17.7 `ATB_BIAS`@-16.3 `VSS`@-13.4 `VDD`@-10.4 `OUTN`@-8.9 `OUTP`@-8.2

## 7. Published cells (`generated/`)

`pt_adc_i` / `pt_adc_q`:
`VDD VSS INP INN VCM VREF IBIAS CLKP CLKN EN ILEN TEST0 TEST1 CODE0..CODE9 DONE OVERLOAD CODEB0..CODEB9 DONEB OVERLOADB ATB_BIAS`

`pt_dac_i` / `pt_dac_q`:
`VDD VSS OUTP OUTN IBIAS CLKP CLKN EN HOLD_ZERO CODE0..CODE9 ATB_BIAS`

Same edge and layer as the staged cells, 1.0 µm pin pitch. No `ACQ0`, `ACQ1`, `PH`. The A/B order of the
published ADC is not exported. Verified numbers are in `README.md`.

## Open items

- The staged candidate is not published and its last revision is not re-reviewed; until it is, the top-level
  regression counts the four converter masters as staged.
- ADC `safe` on the staged candidate: 1.30 µA disabled in the bench window against 1 µA (needs a ruling).
- **OPEN** items above: extracted acquisition windows, DAC setup/hold, one refbuf driving two ADCs, the `VCM`
  source (CNV-06), the clamp in the ADC clock path, duplex at unequal rates.
- Queued extracted runs on the candidate (`scratch/converters-ap4/queue.status`) have not been read back into
  any record here.
