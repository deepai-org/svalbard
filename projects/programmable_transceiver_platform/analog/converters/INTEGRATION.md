# Converter block interface for chip-top integration (adc_i, adc_q, dac_i, dac_q, refbuf)

> **Status 2026-11-13: STAGED CANDIDATE, NOT YET PUBLISHED.** This is the pin contract of the AP4 candidate
> (`CONV_AP4=1`; layouts in `scratch/converters-ap4/stage4/<block>/generated/`: Magic DRC 0, LVS unique,
> KLayout precheck 0/0 on all four). `generated/` still holds the pre-AP4 blocks with `CLKP/CLKN` until the
> candidate's extracted evidence is complete and reviewed. Chip-top should bind to THIS pin list.

Written by the converters owner for the chip-top integration agent (`scratch/chip-top/`). It answers MW-3,
MW-6 and MW-22 of `scratch/reviews/mode-walk.md`. Items marked **OPEN** are not yet backed by a simulation.
All pins are Metal4 (0.4 um wide on a 0.7 um pitch; VDD/VSS 2 um, VREF 1 um) at the block's north edge, in the
west trunk bank; x positions in section 6. adc_q / dac_q are the same layouts as adc_i / dac_i.

## 1. Clock: single-ended CMOS, no top-level clock cell
Each ADC and DAC has ONE clock pin `CLK`: 3.3 V CMOS, single-ended. There is no differential receiver, no
`CLKP/CLKN`, and the top does not shape or invert the clock. The pin is a gate-only input (safe with the conv
island off) and is gated on the block by the block's own enable: a disabled block does not toggle while the
clock keeps running for another block.

| block | `CLK` source |
|---|---|
| adc_i, adc_q | `clockmux.CONV_CLK` |
| dac_i, dac_q | `rf_tx_clk_out` of the digital macro (DT-6, source-synchronous TX). In a build without that port: `CONV_CLK`. |

### 1.1 ADC
- The acquisition window is made on the block: it opens on the RISING `CLK` edge and closes after an on-block
  delay (one-shot). The sampling instant is the end of that window (a delay-line edge, see section 5).
- `ACQ1:0`, static, from `adc_*.config.acquisition_ns[1:0]`, same value for I and Q:
  `0` nominal window (reset value), `1` short, `2` long, `3` debug: window = `CLK` high time, sampling on the
  falling `CLK` edge. Code 3 only fits when 2 x T_clk - T_high covers the conversion (39.1 ns worst case): with a
  50 % clock that is <= 37 MHz interleaved at ss, and it does not fit single-core operation above ~11 MHz. It is
  a bring-up option, not a mission mode.
- `CLK` requirements (codes 0-2): <= 40 MHz; high time and low time each >= selected window + 1 ns (at 40 MHz any
  duty from 40 % to 60 % with the nominal or short window); rms jitter <= 20 ps (assumed bound, section 5).
- `ILEN = 1`: two interleaved cores, one sample per `CLK` period (40 MS/s at 40 MHz). `ILEN = 0`: core A only,
  one sample per period, `CLK` <= 20 MHz. `ILEN` needs a new static register bit (`adc_*.config.interleave`).
- `PH` (output, new): interleave phase. `PH = 0`: the next rising `CLK` edge starts an acquisition in core A,
  `PH = 1`: in core B. It changes about 5-8 ns after a rising edge (end of the window) and is stable at the
  next rising edge. With `ILEN = 0` it stays 0.
- Enable: the block gates the clock with `EN` delayed by 5-10 ns. If `EN` rises while the clock runs, the first
  acquisition can be a runt. Rule: discard the first 4 samples after `EN` rises or after the clock is started or
  re-selected (the clockmux can emit a runt on a select change). The A/B order never has to be inferred: use `PH`.

### 1.2 DAC
- Captures `CODE9:0` on the FALLING `CLK` edge, on the block (DT-6: the macro launches on the rising edge of
  `rf_tx_clk_out`). Do not swap or invert at the top. The output updates one clock period after the capturing
  edge (two register stages in `dac_logic`).
- Setup/hold of `CODE` to the falling edge at the block pins: **OPEN**, not characterised on the candidate; DT-6
  budgets 0.6 ns. Any `CLK` rate <= 80 MHz.
- Enable: if `EN` rises while `CLK` is high the registers can see one runt clock as they leave reset. Enable with
  `HOLD_ZERO = 1` (its reset value: the registers then load mid-scale whatever the clock does) and release
  `HOLD_ZERO` at least 2 clock periods later.

### 1.3 Duplex (MW-22)
One `CONV_CLK` for ADC and DAC means equal rates (40 MHz: ADC 40 MS/s interleaved, DAC 40 MS/s). The blocks do
not force that: ADC and DAC have separate `CLK` pins, so an 80 MHz `rf_tx_clk_out` on the DACs with a 40 MHz
`CONV_CLK` on the ADCs is possible if timing provides both. Not benched.

## 2. Sample handshake
The converters produce no clocks and no request.
- `rf_rx_clk` = the net on the ADC `CLK` pins (`CONV_CLK`); `rf_tx_clk` = the net on the DAC `CLK` pins.
- ADC outputs per core: `CODE9:0`, `DONE`, `OVERLOAD` (core A) and `CODEB9:0`, `DONEB`, `OVERLOADB` (core B).
  10-bit two's complement, bit 9 = MSB; wire as `{CODE, 2'b00}` into the 12-bit MSB-justified field. A core's
  register is written when its conversion ends (`adc_code_reg`, clocked by the conversion-done event) and holds
  until its next conversion ends.
- Capture rule with `ILEN = 1` (one flop stage clocked by rising `CONV_CLK`): at every rising edge read `PH`;
  if `PH = 0` register core A's word, if `PH = 1` core B's word. That word is the sample acquired two edges
  earlier; it has been stable since at most 45 ns after its own edge (39.1 ns conversion + window) and stays
  stable for at least 20 ns after the capturing edge. `PH`, `CODE*` and `CODEB*` are asynchronous to nothing else:
  all change only as a consequence of `CONV_CLK` edges, so this is a same-clock path with >= 4 ns setup at ss.
  `rf_rx_valid` = `EN` AND (4 edges counted since enable / clock start).
- With `ILEN = 0`: register core A at every rising edge (sample of the previous edge).
- `DONE` / `DONEB`: level flags, high from the end of a conversion until that core's next window opens. Status
  only (e.g. a stuck-conversion check); do not clock anything with them.
- `rf_tx_request`: the DAC has no request output; tie high (one code per `CLK` period).
- `CODE*`, `CODEB*`, `DONE*`, `OVERLOAD*`, `PH` cross from the conv island into the core: island isolation clamps.

## 3. References and bias
| pin | block | connect to | notes |
|---|---|---|---|
| `VREF0` | refbuf | `core_bias.VREF0` (5/6 VBG = 1.0 V) | gate input, no DC load. Net `VREF0_CONV` must contain the core_bias pin (MW-6). |
| `VREF` | refbuf (out), adc_i, adc_q | one net `VREF_CONV` | one refbuf for both ADCs (**OPEN**: benched with one ADC only so far). >= 2 um wide, star from the refbuf, away from clocks. ATB node `conv_vref`. |
| `VCM` | adc_i, adc_q | `core_bias.VCM` (VDD/2) | net `VCM_CONV` must contain the core_bias pin (MW-6). **OPEN (risk CNV-06)**: the source is a 40 kohm divider without decoupling, see section 5. |
| `IBIAS` | adc_i, adc_q, dac_i, dac_q, refbuf | one 10 uA `conv` leg of core_bias each, sourced INTO the pin | NMOS diode to VSS inside. On the ADC nothing uses the diode any more (it biased the removed clock receiver); keep the leg bound: `ATB_BIAS` then shows that bias arrives. |
| `ATB_BIAS` | adc_*, dac_* | ATB leaves `adc_comparator_bias`, `dac_bias` | observation only; never drive in mission mode. |
| `VDD`, `VSS` | all | `VDD_CONV_SW`, core ground | |

## 4. Pin lists (subcircuit port order of `<block>.spice`)
`pt_adc_i` / `pt_adc_q`:
`VDD VSS INP INN VCM VREF IBIAS CLK ACQ0 ACQ1 EN ILEN TEST0 TEST1 CODE0..CODE9 DONE OVERLOAD CODEB0..CODEB9 DONEB OVERLOADB ATB_BIAS PH`

`pt_dac_i` / `pt_dac_q`:
`VDD VSS OUTP OUTN IBIAS CLK EN HOLD_ZERO CODE0..CODE9 ATB_BIAS`

`pt_refbuf` (unchanged): `VDD VSS VREF0 VREF IBIAS EN OVR READY`

| pin | dir | type | chip-top source / sink |
|---|---|---|---|
| adc `INP/INN` | in | analog diff, CM 1.65 V, about +-0.9 V diff full scale | `bbfilter_*.out_rx` (`ADCI_P/N`, `ADCQ_P/N`) |
| adc `CLK` | in | CMOS | `clockmux.CONV_CLK` |
| adc `ACQ0, ACQ1` | in | CMOS static | `adc_*.config.acquisition_ns[1:0]` (I and Q equal) |
| adc `EN` | in | CMOS | `adc_*.config.enable` AND state active |
| adc `ILEN` | in | CMOS static | new bit `adc_*.config.interleave` |
| adc `TEST0, TEST1` | in | CMOS static | `adc_*.config.input_test[1:0]` |
| adc `PH` | out | CMOS | digital macro (A/B select of the RX sample register) |
| adc `CODE*, CODEB*, DONE, DONEB, OVERLOAD, OVERLOADB` | out | CMOS | digital macro RF RX input |
| dac `CODE9:0` | in | CMOS | `rf_tx_sample` bits [11:2] (I) / [23:14] (Q), two's complement |
| dac `CLK` | in | CMOS | `rf_tx_clk_out` (falling-edge capture on the block) |
| dac `EN`, `HOLD_ZERO` | in | CMOS | `dac_*.config.enable` AND state; `dac_*.config.hold_zero` |
| dac `OUTP/OUTN` | out | analog diff | `DACI_P/N`, `DACQ_P/N` |

## 5. Numbers behind the contract
Acquisition window (schematic one-shot, 60 fF load, 40 MHz; `scratch/converters-ap4/val/shaper19/shaper.json`.
These were taken with an inverter first stage; the candidate's NAND first stage adds a few tens of ps to the
clock-to-window delay and does not change the width. Extracted values: **OPEN**):

| `ACQ1:0` | tt 27 C 3.3 V | ss 32 C 3.15 V | ff 22 C 3.35 V |
|---|---|---|---|
| 0 nominal | 5.0 ns | 6.1 ns | 4.4 ns |
| 1 short | 3.3 ns | 4.0 ns | 2.9 ns |
| 2 long | 6.3 ns | 7.6 ns | 5.4 ns |
| 3 clock high time | 12.6 ns at 40 MHz / 50 % | same | same |

- Rising `CLK` edge to window start: 0.28-0.42 ns. Conversion budget with `ILEN = 1`: 2 x T_clk - window.
- Codes 0-2: the sampling instant is a delay-line edge with -1.6 ps per mV of `VDD_CONV_SW` (nominal window, tt).
  10 mV of supply ripple correlated with the input moves it by 16 ps: SNR bound 54 dB at 19 MHz, 60 dB at 10 MHz.
- Clock jitter: SNR bound = -20 log10(2 pi f_in sigma); 20 ps rms gives 58 dB at 10 MHz. 20 ps is an assumed
  pessimistic bound for the ring-PLL / prescaler path; no measured figure was found.
- `VCM` source: `core_bias` makes VCM with a 40 kohm (Thevenin) resistive divider and no decoupling. The ADC resets
  its LSB-array node to VCM in every window (charge kicks through the 54.5 fF bridge caps) and, in `input_test`
  1-3, samples VCM on the 0.44 pF top plates (tau about 36 ns against a 5 ns window: those test levels will not
  settle). Every ADC bench so far used an ideal 1.65 V source. A bench with the extracted divider and a second
  ADC's load is queued (`scratch/converters-ap4/realsrc.py`); until it is in, plan for a decoupling capacitor on
  `VCM_CONV`.
- Extracted coupling at the pins (candidate): `INP`-`VCM` 73 fF, `INN`-`VCM` 79 fF (the VCM trunk runs between the
  two inputs so the kicks into VCM are balanced); `CLK`-`PH` 78 fF (both digital).

## 6. Candidate outlines and pin x positions (um; x = 0 at the west edge of the device rows, trunk bank at x < 0)

`adc_i / adc_q`: 480.28 x 936.3 um (0.4497 mm2), bbox x -48.20..432.08, y 0.50..936.80. Pins west to east:
`OVERLOADB`@-44.4 `OVERLOAD`@-43.7 `DONEB`@-39.5 `DONE`@-38.8 `CODEB9`@-36.7 `CODEB8`@-36.0 `CODEB7`@-35.3 `CODEB6`@-34.6 `CODEB5`@-33.9 `CODEB4`@-33.2 `CODEB3`@-32.5 `CODEB2`@-31.8 `CODEB1`@-31.1 `CODEB0`@-30.4 `CODE9`@-29.7 `CODE8`@-29.0 `CODE7`@-28.3 `CODE6`@-27.6 `CODE5`@-26.9 `CODE4`@-26.2 `CODE3`@-25.5 `CODE2`@-24.8 `CODE1`@-24.1 `CODE0`@-23.4 `PH`@-21.3 `CLK`@-20.6 `ACQ1`@-19.9 `ACQ0`@-19.2 `ILEN`@-18.5 `ATB_BIAS`@-17.5 `EN`@-16.5 `IBIAS`@-15.5 `TEST1`@-14.5 `INN`@-13.5 `VCM`@-12.5 `INP`@-11.5 `TEST0`@-10.5 `VREF`@-8.5 `VSS`@-6.0 `VDD`@-3.0

`dac_i / dac_q`: 668.5 x 200.63 um (0.1341 mm2), bbox x -28.50..640.00, y 0.50..201.13. Pins west to east:
`CLK`@-28.2 `CODE9`@-26.8 `CODE8`@-26.1 `CODE7`@-25.4 `CODE6`@-24.7 `CODE5`@-24.0 `CODE4`@-23.3 `CODE3`@-22.6 `CODE2`@-21.9 `CODE1`@-21.2 `CODE0`@-20.5 `HOLD_ZERO`@-19.8 `EN`@-19.1 `IBIAS`@-17.7 `ATB_BIAS`@-16.3 `VSS`@-13.4 `VDD`@-10.4 `OUTN`@-8.9 `OUTP`@-8.2

Published pre-AP4 outlines for reference: adc 465.46 x 1241.16 um, dac 674.50 x 275.93 um; same edge and layer,
1.0 um pitch, `CLKP`/`CLKN` instead of `CLK`, no `ACQ0`/`ACQ1`/`PH`.
