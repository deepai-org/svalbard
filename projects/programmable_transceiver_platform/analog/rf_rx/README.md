# RF receive family: LNA, I/Q mixers, shared baseband filter, BB tap

Transistor-level `lna`, `rxmix_i`, `rxmix_q`, `bbfilter_i`, `bbfilter_q`
(shared RX/TX filter with the PGA as its first stage) and `bb_tap` (reusable
analog observation / injection buffer). Each block has a schematic netlist, a
generated layout, Magic DRC, KLayout DRC cross-check, Netgen LVS, an extracted
netlist with parasitic C and extracted ngspice simulations. All numbers come
from `generated/*.json`; nothing here is silicon or Monte Carlo evidence.

## 1. Files and how to run

| File | Content |
| --- | --- |
| `netlists.py` | writes every `<block>.spice` (single source of the circuits) |
| `<block>.spice` | gf180mcuD devices only; top cell `pt_<block>` |
| `rfrx_flow.py`, `generate_<block>.py` | layout (Magic PCells, rows, M2–M5 routing), DRC, extraction, LVS, GDS export, KLayout DRC |
| `tb.py`, `simlib.py` | ngspice testbenches (schematic or extracted view) |
| `characterize.py` | runs benches; writes `generated/<block>-evidence.json`, `generated/rf_rx_chain.json` |
| `summarize.py` | writes `generated/rf_rx-summary.json` and section 5 of this README |
| `generated/<block>.{gds,mag,ext.spice,lvs.spice}`, `-lvs.txt`, `-layout.json` | layout outputs and DRC/LVS/area records |

```
./run_rf_rx.sh           # full: nominal + 12 corners + chain/LO points (~1 h)
./run_rf_rx.sh --quick   # nominal only
```

Pinned images, `--network none --cpus 3 --memory 6g`: layout, Magic DRC
(`drc(full)`), extraction and Netgen LVS in `svalbard/librelane-gf180-canary:2026.08`
(Magic 8.3.623, Netgen 1.5.316); GDS export (Magic 8.3.678), KLayout DRC and
ngspice in `hpretl/iic-osic-tools@sha256:89641950…`. GDS is exported with the
analog image because canary Magic 8.3.623 does not write the HRES marker (62/0)
for `ppolyf_u_1k` (resistors would be classed as plain P+ poly);
`cif ostyle gdsii` must precede `gds write` after `drc style drc(full)`.
Raw output: `scratch/rf_rx/` (gitignored).

## 2. Common rules

Island rail `VDD` (= `VDD_RF_SW`, 3.3 V), `VSS`. Each block mirrors its bias
from 10 µA sourced into `ibias` (NMOS diode on the pin). Controls are
active-high, gate-only (no current at 3.63 V with the island off). `en=0`
turns every bias, OTA and switch off; `island_off=1` weakly clamps outputs to
VSS (NMOS W/L = 1/10, ~30 µA against an active driver).

## 3. Circuits

**lna (`pt_lna`)** — differential NMOS pair (100/0.28 per side, 20 fingers),
~1 kΩ poly loads, ~4 kΩ drain→gate feedback, 2.8 mA tail (280:1), ~2 pF MIM
input coupling (bottom plate on the pad side, no junction on `RF_RX`) and ~2 pF
output coupling into the mixer node at 1.65 V. PMOS load disconnect when off.
No on-chip inductors (no PDK inductor model); a board L-match is assumed.
`gain_lo` closes a 100/0.28 PMOS shunt across the gates. Bypass
(`rf_lna_bypass`): `byp` closes a 60/0.28 NMOS from the gate node to `rf_out`
with the LNA off.

**rxmix_i / rxmix_q** — double-balanced passive NMOS quad (30/0.28 per switch)
in a hand-placed symmetric cell (`pt_rxmix_quad`, `rfrx_flow.layout_quad`) with
a grounded shield rail between x and lo rails; ~4 pF across the TIA inputs;
pseudo-differential TIA, ~20 kΩ ∥ ~0.4 pF feedback (~20 MHz pole) around the
low-noise OTA `pt_rfrx_otan` (600 µA tail, 600/1 PMOS pair, 20/2 NMOS load,
400 µA output stage, ~5 pF Miller; ~7.1 nV/√Hz at 5 MHz; bias `atb_vbp`
RC-filtered 100 kΩ/2 pF). + inputs at a gated local 1.65 V reference. Offset
DAC `pt_rxmix_ofsdac`: sign-magnitude, 0..31 × 0.4 µA from x_p or x_n at the
TIA summing node (~8 mV/LSB at the filter input, ±250 mV, independent of PGA
gain); FPGA-calibrated. Off: OTA outputs high-Z (external-downconverter inject).
LO assumption: differential 0/3.3 V square, 50 % duty, I/Q in quadrature, gated
off with the mixer; LO pins drive gates only.

**bbfilter_i / bbfilter_q** — pseudo-differential fifth-order all-pole:
stage 1 = PGA real pole (gain = Rf/R1 = 1 + gain0 + 2·gain1 + 4·gain2 + 8·gain3,
0..24 dB, pole independent of gain); stages 2, 3 = unity-gain Tow-Thomas
biquads, Q 1.0 and 0.5 (Butterworth pre-distorted for OTA phase and
parasitics). Unit R ~40 kΩ, unit C 9.6 µm MIM (~0.25 pF); `bw[3:0]` adds
1/2/4/8 unit C per integrator. 14 OTAs `pt_rfrx_otaf` (80 µA tail, 360 µA
output, GBW ~270 MHz, PM ~70°). Every OTA references the input common mode
(`atb_vcm` = 2 × 200 kΩ midpoint across the core inputs), so input-CM error is
not multiplied by PGA gain.

| Path | Condition | Switch |
| --- | --- | --- |
| rx_in → core | en & !dir_tx & !inj | TG |
| tx_in → core | en & dir_tx & !inj | NMOS-only (DAC on conv island) |
| core → out_rx | en & !dir_tx & !rx_direct | NMOS-only (ADC on conv island) |
| core → out_tx | en & dir_tx | TG |
| rx_in → out_rx (filter-less RX) | en & rx_direct | NMOS-only |
| stage-1 bypass | en & byp_s1 (stage-1 OTAs off) | TG |
| stages-2/3 bypass | en & byp_s23 (their OTAs off) | TG |
| obs: 01 rx_in, 10 after PGA, 11 filter out | en & obs_sel | TG |

`inj_p/n` are the core-input nodes; `bb_tap` drives them while `inj=1` opens
both input switches.

**bb_tap (`pt_bb_tap`)** — per leg: NMOS source follower (80/0.28) with 0.5 mA
sink, PMOS supply switch, NMOS-only series switch (60/0.28) to the pad; inject
via NMOS-only switch (40/0.28) pad → `inj_x`. Only NMOS drains touch the pads;
`inj_en` wins over `obs_en`. Pad CM in observe ≈ 0.8 V.

## 4. Ports, controls, ATB

| Block | Port | Connects to |
| --- | --- | --- |
| lna | `rf_in_p/n` | protected RF_RX_P/N pad nodes |
| lna | `rf_out_p/n` | `rf_p/n` of rxmix_i and rxmix_q |
| rxmix_x | `lo_p/n` | I (rxmix_i) / Q (rxmix_q) LO |
| rxmix_x | `bb_p/n` | bbfilter_x `rx_in_p/n` |
| bbfilter_x | `tx_in_p/n` | DAC output (TX input; high-Z when not selected) |
| bbfilter_x | `out_rx_p/n` | ADC input |
| bbfilter_x | `out_tx_p/n` | txmix input (high-Z when not selected) |
| bbfilter_x | `obs_p/n`, `inj_p/n` | bb_tap_x `in_p/n`, `inj_p/n` |
| bb_tap_x | `pad_p/n` | BB_I_P/N or BB_Q_P/N protected pad nodes |

| Block pin | Register field / decode |
| --- | --- |
| lna `en` | `lna.state != off` |
| lna `gain_lo` | `lna.gain.gain_db` in {-6, 0} (two levels only) |
| lna `byp` | `debug.rf_rx_bypass.lna` |
| rxmix_x `en` | `rxmix_x.state != off` |
| rxmix_x `ofs[4:0]`, `ofs_sign` | `pga_x.offset.code`: clamp(code − 128, −31, 31) sign-magnitude, or a new 6-bit field |
| bbfilter `en` / `dir_tx` | `consolidation.bbfilter.direction` != isolated / == tx |
| bbfilter `byp_s1` / `byp_s23` | `debug.rf_bb_bypass.pga` / `.rxfilter` |
| bbfilter `rx_direct` | needs a new register field |
| bbfilter `bw[3:0]` | `rxfilter_x.coefficients.cutoff_code[7:4]` inverted |
| bbfilter `gain[3:0]` | `pga_x.gain` 0..24 dB |
| `rxfilter_x.coefficients.finite_zeros` | no hardware: reserved, reset 0 |
| bbfilter `inj`, bb_tap `inj_en` | `debug.bb_tap.mode` in {inject_rx, inject_tx_filter, inject_tx_mixer} |
| bbfilter `obs_sel`, bb_tap `obs_en` | observe_rx_mixer → 01, observe_rx_pga → 10, observe_rx_filter / observe_tx → 11 |
| inject_tx_mixer | `inj` + `dir_tx` + `byp_s1` + `byp_s23` |
| all `island_off` | island switch `ISO` output |

ATB: lna `atb_nbias` (tail mirror gate, code 16), `atb_vdcm` (drain CM via
2 × 20 kΩ); rxmix `atb_vcm`, `atb_vbp` (code 17); bbfilter `atb_vcm`,
`atb_vbp` (code 19); bb_tap `atb_nbias`. `ibias` 10 µA per instance (7 total).

<!-- RESULTS:BEGIN (rendered by summarize.py from generated/*.json) -->
## 5. Results

### Physical and four-test status

| Block | Area (um2) | Allocation (um2) | Magic DRC | KLayout DRC | LVS | safe | clean | observable | fallback |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| lna | 19639 | 220000 | 0 | 0 | unique match | pass | pass | pass | pass |
| rxmix_i | 76238 | 100000 | 0 | 0 | unique match | pass | pass | pass | pass |
| rxmix_q | 76238 | 100000 | 0 | 0 | unique match | pass | pass | pass | pass |
| bbfilter_i | 406239 | 430000 | 0 | 0 | unique match | pass | pass | pass | pass |
| bbfilter_q | 406239 | 430000 | 0 | 0 | unique match | pass | pass | pass | pass |
| bb_tap | 9978 | none | 0 | 0 | unique match | pass | pass | pass | pass |

### Extracted performance vs target (tt, 27 C, 3.3 V unless a corner table is given)

**lna**

| Metric | Target | Extracted | Schematic |
| --- | --- | --- | --- |
| voltage gain into 50 ohm/leg mixer-input model, 2.4 GHz (dB) | 20 (gain code 3) | -11 | -9.85 |
| NF, 100 ohm diff source, no board match (dB) | 6.0 | 11.8 | n/a |
| NF with ideal lossless board L-match (dB) | 6.0 | 3.28 | n/a |
| differential input impedance at 2.4 GHz (ohm) | 100 (board matching allowed) | 4.29, -161 | n/a |
| gain_lo step (dB) | codes -6/0/10/20 dB | -2.96 | n/a |
| supply current active (mA) | 3.0 | 2.75 | n/a |
| IIP3 (dBm) | 0.0 | n/a | n/a |
| chain NF incl. noise folding (transient noise, I output), board match: 5-9 MHz / 2-9 MHz band (dB) | 6.0 | 12.1, 14.1 | n/a |
| same with a board LNA (15 dB gain, 1.5 dB NF) ahead of the on-chip LNA (dB, Friis), 5-9 / 2-9 MHz |  | 2.77, 3.41 | n/a |
| chain NF via the LNA bypass (unmatched), 5-9 / 2-9 MHz, and with the board LNA 5-9 / 2-9 MHz (dB) |  | 22.2, 26.5, 8.23, 11.9 | n/a |
| RF pad -> I/Q baseband conversion gain with LNA, no board match (dB) |  | gain_i_db=15.3, gain_q_db=14.6 | n/a |
| same with ideal lossless board L-match (dB) |  | gain_i_db=26.3, gain_q_db=26.8 | n/a |

corner sweep (ext, active): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| gain_db | -11.8 | -10.5 |
| nf_db | 11.3 | 12.5 |
| idd_a | 0.00256 | 0.00284 |
| zin_re_ohm | 3.77 | 4.99 |
| zin_im_ohm | -163 | -158 |

**rxmix_i**

| Metric | Target | Extracted | Schematic |
| --- | --- | --- | --- |
| conversion gain, 300 ohm/leg source, 2.4 GHz LO, 5 MHz IF (dB) | 0 (arch, voltage) | 19.3 | 20.1 |
| supply current (mA) | 1.0 | 1.9 | n/a |
| baseband output CM (V) | 1.65 | 1.61 | n/a |
| TIA output offset raw / after FPGA calibration with the offset DAC (V); DAC LSB (V) | |residual| < 10 mV referred to the filter input | -0.0542, -0.00337, -0.0086 | n/a |
| chain with LNA (see lna evidence) |  | gain_i_db=15.3, gain_q_db=14.6 | n/a |

offset calibration across the envelope (ext; calibrated at each point): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| raw_offset_v | -0.0586 | -0.0449 |
| lsb_v | -0.0102 | -0.00691 |
| code | -7 | -5 |
| residual_v | -0.00454 | 0.00262 |

corner sweep (ext transient): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| conversion_gain_db | 17.7 | 20.5 |
| idd_a | 0.00179 | 0.00195 |
| bb_offset_v | -0.0689 | -0.0467 |

**rxmix_q**

| Metric | Target | Extracted | Schematic |
| --- | --- | --- | --- |
| conversion gain, 300 ohm/leg source, 2.4 GHz LO, 5 MHz IF (dB) | 0 (arch, voltage) | 19.3 | 20.1 |
| supply current (mA) | 1.0 | 1.9 | n/a |
| baseband output CM (V) | 1.65 | 1.61 | n/a |
| TIA output offset raw / after FPGA calibration with the offset DAC (V); DAC LSB (V) | |residual| < 10 mV referred to the filter input | -0.0542, -0.00337, -0.0086 | n/a |
| chain with LNA (see lna evidence) |  | gain_i_db=15.3, gain_q_db=14.6 | n/a |

offset calibration across the envelope (ext; calibrated at each point): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| raw_offset_v | -0.0586 | -0.0449 |
| lsb_v | -0.0102 | -0.00691 |
| code | -7 | -5 |
| residual_v | -0.00454 | 0.00262 |

corner sweep (ext transient): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| conversion_gain_db | 17.7 | 20.5 |
| idd_a | 0.00179 | 0.00195 |
| bb_offset_v | -0.0689 | -0.0467 |

**bbfilter_i**

| Metric | Target | Extracted | Schematic |
| --- | --- | --- | --- |
| RX -3 dB cutoff, widest (bw=0) (Hz) | >= 10e6 at tt and in the envelope (lead, Wi-Fi 20 MHz) | 1.52e+07 | 1.78e+07 |
| RX -3 dB cutoff, narrowest (bw=15) (Hz) | 1e5 min | 7.76e+05 | n/a |
| passband peaking at bw=0 (dB above DC) | <= 1 dB ripple | 1.7 | n/a |
| PGA gain range (dB, gain=0 .. 15) | -6 .. 42 in 3 dB steps | -0.0581, 23 | n/a |
| TX direction (tx_in -> out_tx) cutoff and gain |  | dc_gain_db=-0.028, f3db_hz=1.52e+07, peak_gain_db=1.66 | n/a |
| stretch: gain at 20 MHz with widest setting (dB) (40 MHz channels need ~20 MHz corner) |  | -15.5 | n/a |
| supply current, RX active (mA) | 4.5 | 5.82 | n/a |
| output CM minus input CM with input CM at 1.75 V (V), gain 1 / gain 16 (OTAs reference the input CM) | no PGA-gain multiplication | 0.000194, 0.0016 | n/a |
| passband peaking at max PGA gain (dB above DC) | <= 1 dB ripple | 0 | n/a |
| TX observe through bb_tap into 10 pF: -3 dB (Hz) / gain (dB) / HD3 at 0.4 and 0.8 Vpk diff (dBc) |  | 1.51e+07, -1.4, -67.3, -71.7 | n/a |
| TX->RX direction switch settling to 1 % (s) | 1e-06 | 3e-07 | n/a |

corner sweep (ext, RX widest, gain 0): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| f3db_hz | 1.13e+07 | 2.12e+07 |
| dc_gain_db | -0.0741 | -0.0547 |
| peak_gain_db | 0.719 | 3.69 |
| idd_a | 0.00555 | 0.00594 |
| out_cm_v | 1.65 | 1.65 |

corner sweep (ext, RX gain 15): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| dc_gain_db | 22.8 | 23.1 |
| f3db_hz | 8.45e+06 | 1.87e+07 |
| out_cm_v | 1.65 | 1.65 |

**bbfilter_q**

| Metric | Target | Extracted | Schematic |
| --- | --- | --- | --- |
| RX -3 dB cutoff, widest (bw=0) (Hz) | >= 10e6 at tt and in the envelope (lead, Wi-Fi 20 MHz) | 1.52e+07 | 1.78e+07 |
| RX -3 dB cutoff, narrowest (bw=15) (Hz) | 1e5 min | 7.76e+05 | n/a |
| passband peaking at bw=0 (dB above DC) | <= 1 dB ripple | 1.7 | n/a |
| PGA gain range (dB, gain=0 .. 15) | -6 .. 42 in 3 dB steps | -0.0581, 23 | n/a |
| TX direction (tx_in -> out_tx) cutoff and gain |  | dc_gain_db=-0.028, f3db_hz=1.52e+07, peak_gain_db=1.66 | n/a |
| stretch: gain at 20 MHz with widest setting (dB) (40 MHz channels need ~20 MHz corner) |  | -15.5 | n/a |
| supply current, RX active (mA) | 4.5 | 5.82 | n/a |
| output CM minus input CM with input CM at 1.75 V (V), gain 1 / gain 16 (OTAs reference the input CM) | no PGA-gain multiplication | 0.000194, 0.0016 | n/a |
| passband peaking at max PGA gain (dB above DC) | <= 1 dB ripple | 0 | n/a |
| TX observe through bb_tap into 10 pF: -3 dB (Hz) / gain (dB) / HD3 at 0.4 and 0.8 Vpk diff (dBc) |  | 1.51e+07, -1.4, -67.3, -71.7 | n/a |
| TX->RX direction switch settling to 1 % (s) | 1e-06 | 3e-07 | n/a |

corner sweep (ext, RX widest, gain 0): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| f3db_hz | 1.13e+07 | 2.12e+07 |
| dc_gain_db | -0.0741 | -0.0547 |
| peak_gain_db | 0.719 | 3.69 |
| idd_a | 0.00555 | 0.00594 |
| out_cm_v | 1.65 | 1.65 |

corner sweep (ext, RX gain 15): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| dc_gain_db | 22.8 | 23.1 |
| f3db_hz | 8.45e+06 | 1.87e+07 |
| out_cm_v | 1.65 | 1.65 |

**bb_tap**

| Metric | Target | Extracted | Schematic |
| --- | --- | --- | --- |
| observe gain in -> pad, 10 pF || 100 k load (dB) | ~0 (buffer) | -1.37 | -1.37 |
| observe -3 dB bandwidth into 10 pF (Hz) | >= 20e6 | 7.65e+07 | n/a |
| gain at 20 MHz (dB), AC / transient 0.4 Vpp diff |  | -1.66, -1.66 | n/a |
| pad common mode in observe (V) |  | 0.818 | n/a |
| inject pad -> chain node gain (dB) |  | -0.0357 | n/a |
| supply current observing (mA) |  | 1.01 | n/a |

corner sweep (ext observe): min / max over 12 corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)

| Quantity | min | max |
| --- | --- | --- |
| lf_gain_db | -1.48 | -1.28 |
| f3db_hz | 7.08e+07 | 8.21e+07 |
| gain_20mhz_db | -1.81 | -1.53 |
| pad_cm_v | 0.704 | 0.933 |
| idd_a | 0.000996 | 0.00103 |

### RF chain (extracted LNA + both extracted mixers, ideal LO)

| Case | LO (Hz) | I gain (dB) | Q gain (dB) | Supply (mA) |
| --- | --- | --- | --- | --- |
| ext_u | 2.4e+09 | 15.3 | 14.6 | 6.55 |
| ext_m | 2.4e+09 | 26.3 | 26.8 | 6.55 |
| ext_byp | 2.4e+09 | 10.9 | 12.6 | 3.82 |
| ext_m_1200MHz | 1.2e+09 | 36.3 | 36.2 | 6.57 |
| ext_m_600MHz | 6e+08 | 36.4 | 36.4 | 6.58 |
| tnoise_lna_matched | n/a | 28.9 | n/a | n/a |
| tnoise_bypass | n/a | 14.1 | n/a | n/a |

<!-- RESULTS:END -->
## 6. Four-test basis

States are computed by `characterize.py` from extracted simulations (thresholds
in the code).

- **safe**: reset supply current with controls at 0; island-unpowered pin
  currents with controls at 3.63 V and shared nodes forced to 1.65/3.63 V at
  0/27/85 °C. Shared nodes (RF_RX pad, BB pads, DAC input, ADC output) see no
  PMOS junction to `VDD_RF_SW`. Not covered: latch-up review, brownout, ESD.
- **clean**: Magic DRC 0, Netgen unique match, KLayout DRC 0 on the exported
  GDS, extracted tt/27 °C/3.3 V run showing basic function. Corners reported only.
- **observable**: ATB ports on every block; BB observation mux simulated through
  all three taps. No status bits.
- **fallback**: every bypass/inject switch in the routes is implemented and
  simulated in its route configuration; disabled loading reported as switch
  off-capacitance.

Evidence currency: `netlists.py` changed after `lna-evidence.json` /
`lna-layout.json` were written; rerunning it regenerates all six `.spice`
files byte-identically, so the LNA results still apply (rerun
`run_rf_rx.sh` to refresh the hash). All other records match current sources.

## 7. Limitations and open items

1. **Mixer DC offset** from LO coupling in the routed connections to the quad:
   raw −45..−59 mV at the TIA output over the envelope (−47..−69 mV with an RF
   tone). Calibrated per envelope point with the offset DAC (codes −5..−7) the
   residual is ≤ 4.5 mV (target 10 mV); one tt code reused everywhere leaves
   more, so the FPGA should recalibrate on temperature/supply change. Filter OTA
   offsets are not corrected.
2. **Chain NF** (`tb.chain_tnoise`, transient noise with real LO switching,
   I output): 12.1 dB in 5–9 MHz (14.1 dB over 2–9 MHz), 22.2 dB via the LNA
   bypass; with a board LNA (15 dB, 1.5 dB NF): 2.8 dB, or 8.2 dB via bypass.
   ±1.5 dB statistical uncertainty; switch, VCM/bias and sub-2 MHz flicker noise
   not modelled. Dominated by TIA noise through the modest LNA gm (3 mA budget).
3. **LNA**: −11 dB voltage gain into the 50 Ω/leg model, NF 3.3 dB only with an
   ideal board match, Zin 4.3 − j161 Ω unmatched; IIP3/P1dB and real board S11
   not simulated; only two gain levels (gain_lo step −3 dB).
4. **Filter**: widest cutoff 15.2 MHz tt, 11.3–21.2 MHz over corners (≥ 10 MHz
   holds); narrowest 0.78 MHz; 1.7 dB peaking at tt widest (up to 3.7 dB at
   corners, target ≤ 1 dB); PGA 0..23 dB (target −6..42 dB); 5.8 mA per path
   (target 4.5 mA). Fixed Qs, finite zeros not implemented.
5. **Mixer**: 1.9 mA (target 1.0 mA); output CM 1.61 V, which the filter passes
   through to the ADC/txmix.
6. **bb_tap**: pad CM ~0.8 V (external ADC must accept it); NMOS-only switches
   limit inject to ≲ 2 V on the pad.
7. **Layout sensitivity**: extracted/schematic cutoff ratio ~0.86; recheck
   extracted bandwidth after any re-layout.
8. LO modelled as ideal 0/VDD square (LO generator not co-simulated); I/Q
   mismatch, IIP2/IIP3, LO leakage, Monte Carlo, aging and EM of the 0.4 µm M4
   LNA supply tracks not covered.

Stretch (non-gating): 20 MHz corner only at fast corners (−15.5 dB at 20 MHz,
tt); RX active current 18.2 mA (LNA 2.75 + 2 × 1.90 + 2 × 5.82), +1.0 mA per
observing tap; LO /2 and /4: 36 dB conversion gain at 1.2 GHz and 600 MHz LO vs
26–27 dB at 2.4 GHz (ideal board match, `generated/rf_rx_chain.json`).
