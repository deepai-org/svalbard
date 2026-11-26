# Converter family: `adc_i`, `adc_q`, `dac_i`, `dac_q`, `refbuf`

Converter island (`conv`, rail `VDD_CONV_SW`, 3.3 V). Each block has a transistor-level schematic
(`<block>.spice`, top cell `pt_<block>`), a generated Magic layout, GDS, Magic DRC, Netgen LVS, an extracted
netlist (parasitic C only) and extracted ngspice runs. `generated/<block>-evidence.json` is the record of
the four tests (safe, clean, observable, fallback). The chip-top pin contract is `INTEGRATION.md`.

## Blocks (published in `generated/`, 2026-11-22)

| Block | Function | Ports | GDS outline (read-back) |
| --- | --- | --- | --- |
| `refbuf` | OTA + NMOS source follower buffering `VREF0` (1.0 V) to `VREF`, MIM reservoir; `OVR = 1` = high-Z output for ATB forcing | `VDD VSS VREF0 VREF IBIAS EN OVR READY` | 393.5 × 300.56 µm (unchanged) |
| `adc_i`, `adc_q` | 10-bit asynchronous SAR, two cores time-interleaved (`ILEN = 1`: one sample per `CLK`; `ILEN = 0`: core A, ≤ 20 MS/s). Single-ended CMOS `CLK`, on-block acquisition one-shot (`ACQ1:0`), interleave phase output `PH`, enable gate on `EN_D`. Code register macro `adc_code_reg`. | `VDD VSS INP INN VCM VREF IBIAS CLK ACQ0 ACQ1 EN ILEN TEST0 TEST1 CODE0..9 DONE OVERLOAD CODEB0..9 DONEB OVERLOADB ATB_BIAS PH` | 480.28 × 936.30 µm, 0.4497 mm² |
| `dac_i`, `dac_q` | 10-bit current-steering DAC (63 × 16 LSB thermometer + binary 8/4/2/1), cascoded NMOS sources, CM loop to VDD/2, registered decode `dac_logic`; captures `CODE` on the falling `CLK` edge | `VDD VSS OUTP OUTN IBIAS CLK EN HOLD_ZERO CODE0..9 ATB_BIAS` | 668.50 × 200.63 µm, 0.1341 mm² |

`adc_q` / `dac_q` are the same generator output as `adc_i` / `dac_i` under another top-cell name (same GDS
geometry). Chip-top pin contract: `INTEGRATION.md`. `CONV_AP4=0` rebuilds the superseded differential-clock blocks
for comparison only.

**Layers (ASM-8).** Pins: Metal4 labels on Metal4 trunks touching the north edge (`generated/<block>-gdscheck.json`).
**Metal5 exception:** MIM top-plate straps only (`cap_mim_2f0_m4m5` needs Metal5): ADC 7 518 µm² in 128 polygons
inside x 0.4–406.7, y 115.3–578.9 µm; DAC 1 382 µm² in 6 polygons inside x 240.5–316.4, y 20.4–45.1 µm. The rest of
Metal5 is free for the grid. Metal4 is the block's.

## Verified on the published GDS (2026-11-22)

| Check | adc_i | adc_q | dac_i | dac_q | Record |
| --- | --- | --- | --- | --- | --- |
| Magic DRC | 0 | 0 | 0 | 0 | `generated/<block>-drc.txt` |
| Precheck deck (`kl_block_drc --publish`) main / antenna | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | `generated/<block>-kldrc.json` (sha-bound) |
| Read-back LVS (Magic reads the GDS from disk, netgen, parameters compared) | unique | unique | unique | unique | `generated/<block>-lvs-readback.json` |
| Negative controls: W × 1.5 / gate–drain swap | property errors / no match (both fail) | same | same | same | same |
| Pins vs `chip.conn` / on edge Metal3–4 | exact / all | exact / all | exact / all | exact / all | `generated/<block>-gdscheck.json` |
| Markers in read-back GDS vs devices | MIM 64 = CAP_MK 64 = 64 caps; no resistors | same | MIM 3 = CAP_MK 3; HRES 8 = 8 ppolyf_u_1k (RES_MK 16) | same | same |

MOD-22: converter netlists (schematics and Magic extractions) carry PDK MOS as X instances (scan: 0 M lines);
`CONV_MC_SEED=<n>` turns on `sw_stat_mismatch` in every bench (`convkit.models`). Known answer
(`mc_selftest.py`, `generated/mc-selftest.json`): matched nfet_03v3 pair W 10 / L 1 µm, 60 seeds, σ(ΔVgs) 2.37 mV
against 2.45 expected (±20 %): pass; negative controls (mismatch off, M-line rewrite) σ = 0. No converter Monte
Carlo has been run yet.

R+C extraction (`rcext.py`, method of MANDATE 4a): extresist tolerance 0 on the flattened GDS, ground C rebuilt per
net from the C-only extraction of the same GDS (ADC 35.73 → 13.30 pF, DAC 11.02 → 5.41 pF), coupling totals equal to
the C-only netlist (14.52 / 6.09 pF). Coverage of routed nets (> 2 fF): ADC 584/596 (missing: EN_D, enable delay
line EDL_*, shaper taps Kt*/KD*), DAC 338/360 (missing: resistor terminals CMR/CMS/CMRA/CMRB, macro-internal
nets). VDD/VSS resistance not extracted (ideal supplies in all benches).

Extracted ADC evidence (C-only, `generated/adc_i-evidence.json`, `--corners minimal`, tt 27 °C 3.3 V, 40 MS/s):
clean = pass (all conversions done, t_done max 30.36 ns of 44, supply 5.70 mA, VREF 83.0 µA);
safe = **fail** (EN=0 current 1.30 µA in the 1–9 ns bench window against 1 µA; settled 18 nA at 200–290 ns);
fallback = **open** (disabled input 197.6 fF against 100 fF); observable = open. The record's corner sweep is
empty (minimal run): not a corner pass.

## Known misses and not-yet-run items (current state)

- Extracted R+C key runs on the GDS with the ASM-16a port diodes (2026-11-26, `rc_bench.py`, 64-point FFT,
  `generated/<block>-rc-<tag>.json`); ENOB after per-core offset/gain correction: tt 27 °C 3.3 V 40 MS/s 5.02 (SFDR
  41.5 dB, DONE ≤ 33.5 ns); ff 22 °C 3.35 V 4.62 (39.4 dB, ≤ 25.8 ns); ss 32 °C 3.15 V at 39.06 MS/s 5.20 (44.6 ns);
  ss trimmed 3.5 V at 40 MS/s 5.14 (adc_q the same); **ss 32 °C 3.15 V untrimmed at 40 MS/s 4.14 with 9 of 64
  conversions late (MOD-04, CNV-07; 4.33 / 7 late before the diodes)**: ss dies need the 3.5 V trim at 40 MS/s.
  DAC static (dac_i, dac_q identical): full scale ±1.02 V tt, ±1.21 V ss, ±0.84 V ff against ±1.0 V; worst code
  error 0.92 LSB tt, 1.49 ss, 0.54 ff (limit 4). Diodes changed none of these by more than run noise.
- ADC `safe` 1.30 µA vs 1 µA (CNV-07); ADC disabled input load 197.6 fF vs 100 fF (CNV-02); ADC over its 350 000 µm²
  ceiling (452 046 µm² Magic bbox).
- DAC four-test evidence not regenerated on this GDS (the bench runs ~12 h); the earlier records were deleted as
  superseded (CNV-09). DAC dynamic linearity not run (CNV-03); mismatch not simulated (CNV-05).
- `VCM` source is a bare 40 kΩ divider, benches use an ideal source (CNV-06). Clamp in the ADC clock path: CNV9-1.
- No noise or PSRR run. 5 V cells at 3.3 V without Liberty sign-off (CNV-04).

## Files and flow

| Path | Role |
| --- | --- |
| `circuits.py` | block netlists (default = published; `CONV_AP4=0` = superseded pre-AP4 blocks) |
| `lvs_readback.py`, `gds_check.py` | read-back LVS with negative controls; pins / Metal5 / markers on the GDS |
| `rcext.py`, `rc_bench.py` | R+C extraction with C repair; extracted FFT / DAC static runs on it |
| `mc_selftest.py` | Monte Carlo known-answer test (MOD-22) |
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

Risks: CNV-01..07, CNV-09, MOD-04, MOD-05, MOD-06, MOD-13, MOD-22, SUB-01 (`spec/risk-register.md`).
