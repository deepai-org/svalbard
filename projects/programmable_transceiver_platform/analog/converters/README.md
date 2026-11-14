# Converter family: `adc_i`, `adc_q`, `dac_i`, `dac_q`, `refbuf`

Converter island (`conv`, rail `VDD_CONV_SW`, 3.3 V). Each block has a transistor-level schematic
(`<block>.spice`, top cell `pt_<block>`), a generated Magic layout, GDS, Magic DRC, Netgen LVS, an extracted
netlist (parasitic C only) and extracted ngspice runs. `generated/<block>-evidence.json` is the record of
the four tests (safe, clean, observable, fallback). The chip-top pin contract is `INTEGRATION.md`.

## Blocks (published in `generated/`)

| Block | Function | Ports | GDS outline | Supply (extracted, tt) |
| --- | --- | --- | --- | --- |
| `refbuf` | OTA + NMOS source follower buffering `VREF0` (1.0 V) to `VREF`, MIM reservoir. `ACT = EN & ~OVR`; with `OVR = 1` the output is high-Z so the ATB can force `VREF`. `READY` is a lower-bound comparator only. | `VDD VSS VREF0 VREF IBIAS EN OVR READY` | 393.5 × 300.56 µm, 0.118 mm² (Magic bbox) | 0.55 mA |
| `adc_i`, `adc_q` | 10-bit asynchronous SAR, two cores time-interleaved behind one differential clock receiver (`ILEN = 1`: 40 MS/s; `ILEN = 0`: core A alone, 20 MS/s). Top-plate bootstrapped NMOS sampling, monotonic switching from `VREF`, StrongARM comparator, custom 3.3 V SAR logic, code register macro `adc_code_reg`. `TEST1:0` = `input_test` (1: zero, 2/3: ±VREF/4). | `VDD VSS INP INN VCM VREF IBIAS CLKP CLKN EN ILEN TEST0 TEST1 CODE0..9 DONE OVERLOAD CODEB0..9 DONEB OVERLOADB ATB_BIAS` | 465.46 × 1241.16 µm, 0.578 mm² each | 5.73 mA at 40 MS/s |
| `dac_i`, `dac_q` | 10-bit current-steering DAC: 63 thermometer cells of 16 LSB + binary 8/4/2/1, cascoded NMOS sources, on-block common-mode loop (VDD/2), MIM decaps on the bias nodes, registered decode in macro `dac_logic`. Outputs leave through NMOS series switches. `CODEk` = transport bit k + 2 (truncation). | `VDD VSS OUTP OUTN IBIAS CLKP CLKN EN HOLD_ZERO CODE0..9 ATB_BIAS` | 674.50 × 275.93 µm, 0.186 mm² each | 2.07 mA |

- GDS outlines of the ADC and DAC are KLayout measurements (`scratch/converters-ap4/meas/meas.json`, `old_*`
  entries). The evidence files record the Magic bbox (ADC 467.96 × 1242.16, DAC 677.00 × 276.93 µm). The ADC is
  over its 350,000 µm² ceiling (`fits: false`).
- `adc_q` / `dac_q` are the same generator output under another top-cell name. `adc_i.gds` and `adc_q.gds` are
  different builds: `adc_q` has 8 antenna diodes that `adc_i` lacks (3735 vs 3727 devices).
- All controls are active-high and gate-only (safe at 0 V with the island off). Every device on the ADC
  `INP/INN`, `VCM`, `VREF` and on the DAC `OUTP/OUTN` is an NMOS in p-substrate, so a disabled or unpowered
  converter does not clamp the fallback paths (`rf_bb_external_adc`, `rf_tx_external_baseband`).
- Each block takes one 10 µA `IBIAS` sink. ATB nodes: `conv_vref` = `VREF`; `adc_comparator_bias` = ADC
  `ATB_BIAS`; `dac_bias` = DAC `ATB_BIAS`.
- Register fields with no hardware in these blocks: ADC `comparator_trim`; DAC `gain_trim`, `offset_trim`.
- Sample rate: the ADC default in RF modes is 39.0625 MS/s (host resamples 128/125), 40 MS/s selectable
  (`spec/power-delivery.md` section 5.4). All converter evidence is at 40 MS/s.

## Verified numbers

From `generated/<block>-evidence.json` unless another file is named. Extracted netlists, tt/27 °C/3.3 V unless
a corner is given. `python3 summarize.py` appends the full per-metric dump to this file.

| Block | Area µm² (ceiling) | Magic DRC | KLayout DRC | LVS | safe | clean | observable | fallback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| refbuf | 118,270 (150,000) | 0 | 0 | unique | pass | pass | pass | waived (core) |
| adc_i | 581,281 (350,000) | 0 | 0 | unique | pass | pass | pass | open |
| adc_q | 581,281 (350,000) | 0 | 0 | unique | pass | pass | open | open |
| dac_i, dac_q | 187,482 (225,000) | 0 | 0 | unique | pass | fail | pass | pass |

| Item | Value | Source |
| --- | --- | --- |
| ADC conversion, 40 MS/s interleaved | all conversions done at 12/12 corners (tt/ss/ff × 22/32 °C × 3.15/3.35 V); worst 39.1 ns (ss/32 °C/3.15 V) in a 44 ns window; tt 29.96 ns | `adc_i` |
| ADC single core (`ILEN = 0`), 20 MS/s | done at all four ss corners, worst 38.36 ns in 40 ns | `adc_i` |
| ADC transfer | 568 codes/V (full scale ±0.90 V), offsets −4 (A) / −12 (B) codes, ≤ 4 codes from a per-core gain/offset fit | `adc_i` |
| ADC `input_test` 1/2/3 | core A 0 / +126 / −128, core B −14 / +112 / −142 codes | `adc_i` |
| ADC FFT, 256 points, 18.9 MHz, 0.8 V peak, ideal VREF | raw SNDR 29.5 dB; after per-core offset/gain correction SNDR 31.4 dB (ENOB 4.9), SFDR 41.5 dB | `generated/adc_i-fft-u_tt_256_a0p8.json` |
| ADC `VREF` draw | 83 µA average at 40 MS/s | `adc_i` |
| ADC disabled | 0.78 µA (`adc_i`) / 0.87 µA (`adc_q`) in the bench window; input 232 fF powered-off, 209 fF unpowered, < 10 pA at 1.65 V | `adc_i`, `adc_q` |
| DAC full scale | −0.979 / +0.972 V differential, LSB 1.907 mV | `dac_i` |
| DAC static error (13 codes, endpoint fit) | max 2.14 LSB; endpoint spread 0.524 LSB against a 0.5 LSB gate, so `clean` = fail | `dac_i` |
| DAC output common mode | 1.730 V (target 1.65 V) | `dac_i` |
| DAC disabled | 7.4 nA; output 99 fF powered-off, 98 fF unpowered | `dac_i` |
| refbuf `VREF` | 0.9989 V; 0.9977–0.9999 V over 12 corners; 27 mV p-p under 1 mA × 3 ns pulses | `refbuf` |
| refbuf enable to `READY` | 1.56 µs after enable at tt | `refbuf` |

The published GDS of every block is re-extracted and LVS-matched (round trip). Precheck-deck records (`generated/<block>-kldrc.json`, main + antenna, sha-bound to the GDS)
exist for `adc_q`, `dac_i`, `dac_q` only.

## Files and flow

| Path | Role |
| --- | --- |
| `circuits.py` | block netlists; `CONV_AP4=1` selects the staged candidate, unset = the published blocks |
| `lib/convkit.py` | PCell placement, channel router, Magic/Netgen/ngspice wrappers |
| `flow.py` | `harden` (LibreLane macros) and `block` (layout, DRC, LVS, extracted sims, evidence); `CONV_STAGE=<dir>` builds outside `generated/` |
| `benches.py`, `adc_fft.py`, `dac_dynamic.py` | extracted benches; coherent ADC FFT; 80 MS/s DAC dynamic bench |
| `summarize.py` | appends (or rewrites) a generated `RESULTS` section at the end of this file from the evidence files |
| `rtl/`, `generated/macros/` | `dac_logic`, `adc_code_reg` (hardened `gf180mcu_fd_sc_mcu7t5v0` macros), testbenches. `adc_sar_logic` is not in the ADC; its LEF is still read by `circuits.adc()` |

```
./run_converters.sh          # RTL self-checks, LibreLane macros, all blocks, corners (hours)
./run_converters.sh --quick  # reuse committed macros, nominal extracted sims only
python3 flow.py block refbuf # one block
python3 summarize.py         # optional: append the per-metric RESULTS dump
```

Containers run with `--network none`: Magic 8.3.623 / Netgen 1.5.316 / LibreLane in
`svalbard/librelane-gf180-canary:2026.08`; ngspice, Magic 8.3.678 GDS export and KLayout in the analog image
(digests in each evidence file). Raw output goes to `<repo>/scratch/converters/`.

Layout method: single-finger PDK PCells with guard rings in rows, each terminal on a private Metal2 riser into
a Metal3 channel, Metal4 jumpers and a west Metal4 trunk bank with the ports at the north edge, MIM capacitors
on Metal4/5 inside capacitor rows, digital macros placed as GDS subcells.

## Open items

Risks: CNV-01, CNV-02, CNV-03, CNV-04, CNV-05, CNV-06, CNV-07, MOD-04, MOD-05, MOD-06, MOD-13, SUB-01
(`spec/risk-register.md`).

- A repacked candidate with a single CMOS `CLK` pin, on-block acquisition one-shot (`ACQ1:0`) and `PH` output
  is staged in `scratch/converters-ap4/stage4/` (ADC 0.450 mm², DAC 0.134 mm²) and is not published; chip-top
  already binds to its pin list (`INTEGRATION.md`). Its last revision is not re-reviewed, and its ADC `safe`
  test reads 1.30 µA disabled against the 1 µA limit, which needs a ruling.
- `adc_i.gds` has 7 antenna violations (ANT.16_i_ANT.5) and no precheck-deck record
  (`scratch/reviews/signoff-gap.md` 6b).
- The ADC `VCM` source is a bare 40 kΩ divider; every ADC bench uses an ideal 1.65 V source (CNV-06).
- DAC `clean` fails on the endpoint-spread gate; no DAC corner sweep, stretch-rate or `hold_zero` result is in
  the current evidence; random mismatch is not simulated (CNV-03, CNV-05).
- The only DAC dynamic record (`generated/dac_i-dynamic-sch.json`) is a schematic run older than the current
  DAC netlist.
- ADC disabled-input load 232 / 209 fF against the 100 fF fallback limit: `fallback` = open (CNV-02).
- ADC dynamics rest on one tt FFT with an ideal reference (MOD-04); `adc_q` evidence has the nominal run only
  and its `observable` test is open.
- Evidence staleness: `circuits.py`, `lib/convkit.py`, `flow.py`, `benches.py` changed after every evidence
  record; schematics, macros and GDS/extracted netlists still match their hashes (MOD-05).
- `dac_logic` and `adc_code_reg` use 5 V-rated cells at 3.3 V without 3.3 V Liberty sign-off (CNV-04).
- No extraction with metal resistance; no noise, PSRR or Monte Carlo run on any block.
