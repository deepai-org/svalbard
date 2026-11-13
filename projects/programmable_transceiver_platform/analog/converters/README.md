# Converter family: `adc_i`, `adc_q`, `dac_i`, `dac_q`, `refbuf`

Converter island (`conv`, rail `VDD_CONV_SW`, 3.3 V). Each block has a
transistor-level schematic (`<block>.spice`), a reproducible Magic layout
(`generate_<block>.py` → `flow.py`), GDS / flat `.mag`, Magic DRC, Netgen LVS,
an extracted netlist with parasitic C, and extracted ngspice runs.
`generated/<block>-evidence.json` is the authoritative four-test record.

## Status 2026-11-10 (v3 rework in progress; tables below still describe v2 until marked)

* **ADC v3** (`circuits.adc_il`): two v2 SAR cores, time-interleaved behind one
  clock receiver (toggle flip-flop steers alternate SAMPLE pulses); comparator
  latch/reset/clock buffers widened, direct `CMPCLK = NOR3(DP, DN, RUNB)`.
  `ILEN=0` = single core A, v2 behaviour (in-block fallback). New ports
  `ILEN`, `CODEB0..9`, `DONEB`, `OVERLOADB` (interface-changes.md). First v3
  evidence run (00:29 netlist): 40 MS/s per channel passes at tt and every
  envelope corner, single-core 20 MS/s passes at all ss corners (was: fails).
  **Confirmed 02:44 on the regenerated layout** (generated/adc_i-evidence.json):
  clean pass, 40 MS/s at 12/12 envelope corners, single-core 20 MS/s at all
  ss corners, 5.73 mA; 45 MS/s ss margin probe fails. (Magic layout is not
  bit-reproducible run to run, so evidence is always re-run after relayout.)
* **Next (v4, risk register SUB-01):** DNW pockets under adc_i NMOS near the
  digital macro + north p+ ring; ss/ff FFTs deferred to the v4 layout. (risk: SUB-01)
* **DAC v3** (`circuits.dac`): per-cell NMOS cascode (W = 2 x CS, L = 0.5 µm,
  bias 10 µA into a W1/L3 diode, CS Vds ~0.5 V; standalone check: cell
  current changes 0.014 % over a 1.2–2.2 V leg) and an on-block CM loop
  regulating the output CM to VDD/2. dac_i and dac_q netlists regenerated
  from the same generator; both parse in ngspice (schematic and extracted).
* **DAC v4 (2026-11-12, CNV-03/CNV-05)**: 1 pF MIM decaps on ATB_BIAS and VCASC (CK/CLKN couple
  21 fF onto ATB_BIAS); footer NMOS on the VDD/2 CM divider (EN=0 current was 33 µA, now 7 nA).
  Bench: `DAC_T0` 900 ns, per-chunk endpoints (spread gated ≤ 0.5 LSB), only measured vectors saved.
  Extracted tt: max |INL| 2.14 LSB (13 codes), endpoint spread 0.52 LSB → `clean` fails on that gate;
  40 MHz clock ripple still ±2.3 % FS (route isolation needed); random mismatch not simulated.
* **Criteria restored**: `clean` is ≤ 4 codes (10-bit) = 1 LSB8 from a
  gain/offset fit for ADC and DAC (was relaxed to 32); ADC fallback loading
  limit is 100 fF/leg (was moved to 0.5 pF). With 100 fF the v3 ADC
  (2 cores on INP/INN, 209–232 fF) **fails** the fallback criterion; it is
  reported open, not relaxed. (risk: CNV-02)
* FFT bench (`adc_fft.py`): 1024 points, tone bin 487 (19.02 MHz at 40 MS/s,
  near Nyquist), extracted refbuf in the loop, run at tt, ss/32 °C/3.15 V and
  ff/22 °C/3.35 V.

## Files

| Path | Role |
| --- | --- |
| `circuits.py` | block netlists (`refbuf`, `dac`, `adc` analog core, `sar_core` + `adc2` = current ADC) |
| `lib/convkit.py` | PCell placement, channel router, Magic/Netgen/ngspice wrappers |
| `flow.py` | `harden` (LibreLane macros) and `block` (layout → DRC → LVS → sims → evidence) |
| `benches.py`, `adc_fft.py` | extracted ngspice benches; 32-point ADC FFT |
| `summarize.py` | appends/rewrites a detailed generated `## RESULTS` section in this README from the evidence files |
| `rtl/` | `dac_logic`, `adc_code_reg` (hardened), `adc_sar_logic` (protocol reference + RTL self-check), testbenches, LibreLane configs |
| `generated/macros/` | hardened macros: `dac_logic`, `adc_code_reg`; `adc_sar_logic` is not in the current ADC but its LEF is still read by `circuits.adc()` |

## Reproduce

```
./run_converters.sh          # RTL self-checks, LibreLane macros, all blocks, corners (hours)
./run_converters.sh --quick  # reuse committed macros, nominal extracted sims only
python3 flow.py block refbuf # one block
python3 summarize.py         # optional: append per-metric RESULTS dump from evidence
```

Pinned images, always `--network none`, ≤3 CPUs, `OMP_NUM_THREADS=1`:
Magic 8.3.623 / Netgen 1.5.316 / LibreLane in
`svalbard/librelane-gf180-canary:2026.08` (`sha256:b60278092f08…`, PDK
`/pdk/gf180mcuD`); ngspice 43, Magic 8.3.678 GDS export and KLayout DRC in
`hpretl/iic-osic-tools@sha256:89641950…` (local ID `sha256:bd7a702b…`).
Raw output: `<repo>/scratch/converters/`.

## Layout method (`lib/convkit.py`)

Correct-by-construction router, chosen for DRC-clean/LVS-unique results over
density: single-finger PDK PCells (`nfet_03v3`, `pfet_03v3`, `cap_mim_2p0fF`,
`ppolyf_u_1k`) with guard rings in rows; each terminal rises on private Metal2
into a Metal3 channel (left-edge packing; split nets joined by Metal4
jumpers); multi-channel nets use Metal4 jumpers over MOS rows or a west-edge
Metal4 trunk bank (ports labelled on Metal4 at the top edge); MIM caps own
Metal4/5 inside capacitor rows. Digital parts are LibreLane-hardened
`gf180mcu_fd_sc_mcu7t5v0` macros placed as GDS subcells with pins facing the
analog rows (`rtl/flow/*.pins`).

## Blocks

### `refbuf` — reference buffer

NMOS-input OTA (VREF0 vs VREF, 10 µA tail) → 10 pF dominant pole → NMOS source
follower (4×10/0.5) with 500 µA mirrored sink → `VREF`, 100 pF MIM reservoir.
`ACT = EN & ~OVR`; with `ACT=0` VREF sees only NMOS junctions/gates (ATB
force/sense override). `READY` trips at VREF > VREF0 − ~30 mV (lower bound only).

Ports: `VDD VSS VREF0 VREF IBIAS EN OVR READY`.

### `dac_i` / `dac_q` — 10-bit segmented current-steering DAC

63 thermometer cells of 16 LSB + binary 8/4/2/1; NMOS sources (L = 2 µm,
0.978 µA/LSB, 1 mA full scale) mirrored from 10 µA IBIAS; NMOS switch pairs;
two-stage registered update in macro `dac_logic` (two's complement → offset
binary with `hold_zero` → mid-scale; thermometer decode → 67 registered
controls). Load: VDD → PMOS header → 1.1 kΩ → 1 kΩ per leg (±1 V diff at
1 mA). `OUTP/OUTN` leave through NMOS series switches, so a disabled or
unpowered DAC does not load `rf_tx_external_baseband` injection. Local
receiver (40 µA tail) for the low-swing `DAC_CLOCK`.

Ports: `VDD VSS OUTP OUTN IBIAS CLKP CLKN EN HOLD_ZERO CODE0..CODE9 ATB_BIAS`
(`CODEk` = transport `dac_code[k+2]`: truncation of bits [1:0]).

### `adc_i` / `adc_q` — 10-bit asynchronous SAR

* Sampling: top-plate bootstrapped NMOS switch per leg (10 µm, 210 fF boot
  cap). Everything on `INP/INN` is NMOS in p-substrate, so a disabled or
  unpowered ADC does not load the input (`rf_bb_external_adc` fallback).
* CDAC per side: MSB 4/2/1 × 54.5 fF units on the sampling node (≈ 0.44 pF),
  64/63-unit bridge, LSB 32..1 plus dummy. Monotonic downward switching from
  VREF; NMOS-only bottom-plate switches (VREF = 1.0 V).
* Comparator: StrongARM, 8/0.28 input pair, inverter outputs `DP/DN`.
* SAR loop (`circuits.sar_core`): custom 3.3 V static CMOS, ~600 PCell
  transistors in five rows. Per decision an armed NAND latch, a P/N NOR capture
  latch pair and bottom-plate drivers fed directly from the latches; comparator
  clock is a handshake, `CMPCLK = RUN & ~(DP|DN)`. Macro `adc_code_reg` only
  registers the code (`DONE` = 10th decision & EN).
* Sampling-phase controls (bootstrap, top-plate VCM, LSB reset) are decoded
  locally from `SAMPLE`, `EN`, `TEST1:0` with PCell gates.
* `input_test` (`TEST1:0`): 1 = both top plates sample VCM (zero code);
  2/3 = sample VCM with the weight-128 plate of P/N held low → ±VREF/4.
* Timing: `SAMPLE` high (from the `ADC_CLOCK` receiver) = acquisition;
  conversion is self-timed. `acquisition_ns/decision_ns/reset_ns` are set by the
  clock duty cycle, not in this block.

Ports: `VDD VSS INP INN VCM VREF IBIAS CLKP CLKN EN TEST0 TEST1 CODE0..CODE9
DONE OVERLOAD ATB_BIAS`.

## Controls and ATB

| Port | Register field | Notes |
| --- | --- | --- |
| adc `EN` | `adc_*.config.enable` AND state active | 0 = all off, codes/DONE low |
| adc `TEST1:0` | `adc_*.config.input_test` | stopped-only |
| adc — | `comparator_trim`, `acquisition_ns`, `decision_ns`, `reset_ns` | not implemented in the block |
| dac `EN` | `dac_*.config.enable` AND state active | 0 = outputs isolated, no current |
| dac `HOLD_ZERO` | `dac_*.config.hold_zero` | mid-scale |
| dac — | `gain_trim`, `offset_trim` | no analog effect |
| refbuf `EN` | `refbuf.enable` AND state ≠ off | |
| refbuf `OVR` | `debug.bias_override.refbuf` | buffer high-Z for ATB0 force |
| refbuf `READY` | status `refbuf_ready` | |

All controls are active-high, 0 = off, gate-only (safe at 0 V with the island
off). ATB nodes: `conv_vref` = `VREF`; `adc_comparator_bias` = adc `ATB_BIAS`
(clock-receiver tail gate); `dac_bias` = dac `ATB_BIAS` (current-source gate).
Each block needs one 10 µA IBIAS sink.

## Current results (extracted)

| Block | Area µm² (ceiling) | DRC Magic / KLayout | LVS | safe | clean | observable | fallback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| refbuf | 118,270 (150,000) | 0 / 0 | unique | pass | pass | pass | waived (core) |
| adc_i, adc_q | 259,036 (350,000) | 0 / 0 | unique | pass | pass | pass | pass |
| dac_i, dac_q | 187,482 (225,000) | 0 / 0 | unique | pass | fail (endpoint spread 0.52 > 0.5 LSB; INL 2.14 ≤ 4) | pass | pass |

Published GDS (Magic 8.3.678) is re-extracted and LVS-matched; HRES marker
present on every `ppolyf_u_1k`. "clean" = basic function: ADC conversions
complete, monotonic, within 32 codes of a gain/offset fit; DAC ±1 V-class,
monotonic, |error| < 32 LSB. ADC fallback = no DC path and < 0.5 pF/leg.

| Metric | Result |
| --- | --- |
| ADC conversion time | 34.8 ns tt/27 C/3.3 V; ~28 ns ff/22 C/3.35 V; 45 ns ss/32 C/3.15 V |
| ADC rate | correct at 20 MS/s (10 ns acq.) tt and ff; 16 MS/s at ss (20 MS/s fails at ss); 25 MS/s tt codes correct but DONE 0.8 ns late (not claimed); 40 MS/s and 80 MS/s not met (risk: MOD-04) |
| ADC transfer (tt, 20 MS/s) | 586 codes/V (FS ≈ ±0.87 V), offset +7 codes, DC points within 1 code of fit |
| ADC FFT (32 pt, 1.875 MHz, 0.8 V pk diff, 20 MS/s, tt) | SNDR 50.2 dB, ENOB 8.0, SFDR 53.2 dB |
| ADC `input_test` | zero → +14; ±VREF/4 → +126 / −130 (ideal ±128) |
| ADC supply | 2.87 mA at 20 MS/s (allocation 8 mA); 1.7 nA disabled; VREF draw 63 µA |
| ADC input load off/unpowered | 113 / 110 fF, no DC path |
| DAC full scale / error (v4, extracted) | −0.979/+0.972 V diff tt; endpoint-fit error ≤ 2.14 LSB at 13 codes tt; 3.60 LSB ss/32 C/3.10 V, 2.35 LSB ff/22 C/3.35 V (C +15 %); ff full scale 1.566 V (< 1.6 V window) |
| DAC CM / supply (v4, extracted) | 1.73 V tt (target 1.65 V; sch 1.655); 2.07 mA; CM 1.62 V ss, 1.77 V ff; EN=0 7.4 nA |
| DAC stretch | 80 MS/s update with endpoints intact; `hold_zero` 1.6 mV diff |
| refbuf | VREF 0.999 V (12 corners 0.997–0.999 V), 0.55 mA, 27 mV p-p under 1 mA × 3 ns pulses, READY 1.6 µs after enable (~1 µs later at ss) |

`adc_q` / `dac_q` are the same generator output with another top-cell name;
they have their own DRC/LVS/KLayout/nominal extracted run, while test modes,
rate sweeps, FFT and corners were run on the `_i` copies only.

Evidence currency: block netlists and macros match every evidence record, and
`flow.py` regenerates all five `.spice` files byte-identically. Shared scripts
changed after some runs: `circuits.py`, `lib/convkit.py`, `flow.py`,
`benches.py` after `refbuf`, `dac_i`, `dac_q` evidence; `benches.py` after
`adc_i-evidence.json`; `rtl/adc_sar_logic.v`, `rtl/adc_sar_delay.v` after
`dac_i-evidence.json` and `generated/macros/dac_logic.json` (not inputs of
those blocks). `adc_q-evidence.json` and `adc_i-fft.json` are current. (risk: MOD-05)

## Limitations and open items

1. ADC rate: 20 MS/s at tt/ff, 16 MS/s at ss/32 C/3.15 V; the 40 MS/s
   allocation is not met, so 20 MHz Wi-Fi at ss relies on the
   `rf_bb_external_adc` fallback. (risk: CNV-02)
2. ADC dynamics from one 32-point FFT at one corner; no INL/DNL sweep, noise
   or Monte Carlo. No comparator trim (offset +7..+14 codes, digital removal).
   Handshake capture margin (~0.6 ns capture vs ~1 ns reset path, tt) not
   characterised under mismatch. (risk: MOD-04)
3. DAC output CM 1.43 V and VDD/corner-dependent (no CM loop); the TX filter
   must accept it. No glitch, SFDR or full-code INL/DNL run. `gain_trim` /
   `offset_trim` have no effect. (risk: CNV-03)
4. `dac_logic` and `adc_code_reg` are 5 V-rated `mcu7t5v0` cells run at 3.3 V
   without 3.3 V Liberty sign-off. (risk: CNV-04)
5. refbuf `READY` has no upper bound; no noise/PSRR; load model is a pulse
   train, not the ADC. ADC/DAC benches use an ideal VREF. (risk: MOD-13)
6. `circuits.adc2()` builds on `circuits.adc()`, which still instantiates the
   `adc_sar_logic` macro (removed again in `adc2`) and reads its LEF; removing
   that dependency would let `generated/macros/adc_sar_logic.*` and
   `rtl/flow/adc_sar_logic.*` go.
7. Extracted decks take 40–90 min each; coverage is narrow.
