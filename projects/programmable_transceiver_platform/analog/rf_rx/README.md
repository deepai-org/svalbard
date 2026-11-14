# RF receive family: LNA, I/Q mixers, shared baseband filter, BB tap

Transistor-level `lna`, `rxmix_i`, `rxmix_q`, `bbfilter_i`, `bbfilter_q` (shared RX/TX filter with the PGA as its
first stage) and `bb_tap` (analog observation / injection buffer, also used for `WMON`). Numbers come from
`generated/*.json`; nothing here is silicon or Monte Carlo evidence. Exact pin lists, bindings and register
sources: `chip-top-pins.md`. Risks: IDs refer to `spec/risk-register.md`.

## 1. Status

| Block | Cell | State | Area µm² (bbox µm) | DRC Magic / KLayout, LVS | Performance evidence |
| --- | --- | --- | ---: | --- | --- |
| `bbfilter_i`, `bbfilter_q` | `pt_bbfilter_i/q` | published, committed | 341,901 (586.3 × 583.15) | 0 / 0, unique | current: matches netlist and GDS |
| `bb_tap` | `pt_bb_tap` | published on disk; netlist and records not committed | 19,511 (99.08 × 196.92) | 0 / 0, unique | current: matches netlist and GDS |
| `rxmix_i`, `rxmix_q` | `pt_rxmix_i/q` | candidate, not published | 35,442 (192.73 × 183.9) | 0 / 0, unique | same netlist, earlier layout: to be rerun |
| `lna` | `pt_lna` | candidate, not published (review NO-GO) | 42,921 (219.77 × 195.3), plus four spirals | 0 / 0, unique | none valid: evidence is from an older netlist |

Areas and DRC/LVS are from `generated/<block>-layout.json`. `integration/top/pt_chip.conn` binds the cells in
`generated/` (masters `generated/<block>.ext.spice`), including the candidate LNA and mixer pin lists. The
`lna`, `rxmix_*` and `bb_tap` netlists and records in git are older than the cells on disk (see Open items).

## 2. Files and how to run

| File | Content |
| --- | --- |
| `netlists.py` | writes every `<block>.spice` (single source of the circuits; top cell `pt_<block>`) |
| `bbf_fd.py`, `bbf_layout.py`, `bbf_bench.py` | baseband filter circuit, layout and benches (with bench self-tests) |
| `lna_layout.py`, `lna_spiral.py`, `lna_match.py` | compact LNA/mixer layout, spiral cells and models, match and stability benches |
| `rfrx_flow.py`, `generate_<block>.py` | layout, Magic DRC, extraction, Netgen LVS, GDS export, KLayout DRC |
| `tb.py`, `simlib.py`, `linearity.py`, `bench_selftest.py` | ngspice testbenches (schematic or extracted view) and their self-tests |
| `characterize.py` | runs benches; writes `generated/<block>-evidence.json`, `generated/rf_rx_chain.json` |
| `summarize.py` | writes `generated/rf_rx-summary.json` and re-renders section 5 of this file |
| `generated/` | `<block>.{gds,mag,ext.spice,lvs.spice}`, `-lvs.txt`, `-layout.json`, `-kldrc.json`, `-evidence.json` |

```
./run_rf_rx.sh           # full: nominal + 12 corners + chain points (~1 h)
./run_rf_rx.sh --quick   # nominal only
```

Pinned images, `--network none --cpus 3 --memory 6g`: layout, Magic DRC (`drc(full)`), extraction and Netgen
LVS in `svalbard/librelane-gf180-canary:2026.08` (Magic 8.3.623, Netgen 1.5.316); GDS export (Magic 8.3.678),
KLayout DRC and ngspice in `hpretl/iic-osic-tools@sha256:89641950…`. The GDS is exported with the second
image because Magic 8.3.623 does not write the HRES marker (62/0) for `ppolyf_u_1k`. Raw output:
`scratch/rf_rx/` (gitignored). Do not run `run_rf_rx.sh` or `summarize.py` on the working tree until the LNA
redesign is closed: they would replace the filter and tap records with a mixed set.

## 3. Common rules

- Supplies: `VDD` = the rf_rx island rail (3.3 V), `VSS`; `bb_tap` sits on the debug island. The LNA `VSS` is
  `AGND_RX`.
- Bias: each block mirrors 10 µA sourced into `ibias` (NMOS diode on the pin); 8 instances in total including
  the `WMON` tap.
- Controls are static, active high, and drive gates only. `en=0` turns every bias, OTA and switch off;
  `island_off=1` weakly clamps outputs to VSS (NMOS W/L = 1/10).
- LO pins drive NMOS gates only. All RX benches in this directory use an ideal 0/VDD square LO.

## 4. Blocks

### bbfilter_i / bbfilter_q

Fully differential fifth-order Butterworth (`bbf_fd.py`): stage 1 is the PGA and the real pole (inverting
amplifier, gain k/4 from a 6-bit conductance bank, pole independent of gain); stages 2 and 3 are Tow-Thomas
biquads (Q 0.618 and 1.618), each with a +12 dB step (`gainc0`, `gainc1`). Five fully differential two-stage
Miller OTAs with continuous common-mode feedback to `atb_vcm`, so the output common mode follows the input
common mode at every PGA code. Each integrator, its capacitor banks and the resistors on its summing nodes form
one compact macro (MIM over active).

| Control | Function |
| --- | --- |
| `bw[3:0]`, `fc_fine[2:0]` | cap code m = 8·bw + fine (0..127, larger = lower cutoff), reset 8 |
| `qt[3:0]` | Q trim, Q = q_top·(1 − 0.032·k), reset 6 (Butterworth). Validator rule: m ≤ 1 requires qt ≥ 6 |
| `gain[5:0]`, `gainc[1:0]` | PGA −6..+42 dB in 3 dB steps through the 17-entry table `netlists.GAIN_TABLE` |
| `dcf[7:0]`, `dcf_sign` | fine DC-offset DAC into the stage-1 summing nodes, sign-magnitude |
| `obs_sel[1:0]` | observe to `bb_tap`: 01 `rx_in`, 10 after the PGA, 11 filter output |

Cutoff and Q codes are per-part bring-up trims; the calibration entry per PGA code is {cap code, Q code}.

| Path | Condition | Switch |
| --- | --- | --- |
| `rx_in` → core | `en & !dir_tx & !inj` | TG |
| `tx_in` → core | `en & dir_tx & !inj` | NMOS only (DAC is on the conv island) |
| core → `out_rx` | `en & !dir_tx & !rx_direct` | NMOS only (ADC is on the conv island) |
| core → `out_tx` | `en & dir_tx` | TG |
| `rx_in` → `out_rx` (filter-less RX) | `en & rx_direct` | NMOS only |
| stage-1 bypass | `en & byp_s1` (stage-1 OTA off) | TG |
| stages 2/3 bypass | `en & byp_s23` (their OTAs off) | TG |

`inj_p/n` are the core-input nodes; `bb_tap` drives them while `inj=1` opens both input switches.

### bb_tap

Per leg: NMOS source follower (80/0.28) with a 0.5 mA sink and a PMOS supply switch, an NMOS-only series switch
(`nfet_06v0` 100/0.7) to the pad, and an NMOS-only inject switch (`nfet_06v0` 60/0.7) from the pad to `inj_x`.
Only NMOS drains touch the pads; `inj_en` wins over `obs_en`. Each pad-switch gate sits behind 100 kΩ of
`ppolyf_u_1k` with a MIM (8 µm side) from the gate to its pad (`TAP_RG`, `TAP_CC` in `netlists.py`), so the
gate follows the pad during an ESD pulse (PAD-02; screen: `analog/pads/hbm_core_screen.py`). Limits: RFR-09.

### rxmix_i / rxmix_q (candidate)

Double-balanced passive NMOS quad (`pt_rxmix_quad`) into a pseudo-differential transimpedance amplifier around
the low-noise OTA `pt_rfrx_otan` (single tail, no `hib` pin), + inputs at a gated local 1.65 V reference.
Offset DAC `pt_rxmix_ofsdac`: sign-magnitude, 5 bits + sign, at the TIA summing node; calibrated by the FPGA.
Off: OTA outputs high-Z (external-downconverter inject through `bb_tap`).

### lna (candidate)

LC-tuned transconductance stage: pseudo-differential common-source pair (450/0.28 per side, ~10 Ω series gate
resistors, replica gate bias), one cascode (300/0.28) per leg into the tank nodes `tank_p/n`, and a 16 µm MIM
from the tank to each mixer (`rf_out_*` → rxmix_i, `rf_outq_*` → rxmix_q). The tank inductors (`pt_lna_ind`,
170 µm, 3 turns, 1.35 nH) and the on-chip source-degeneration inductors (`pt_lna_deg`, 140 µm, 2 turns,
0.47 nH) are separate DRC-only spiral cells placed at assembly; there are no source pads. Controls: `ct[3:0]`
tank tune (reset 7); `att[4:0]` + `gain_lo` (MSB) attenuator; `lobias` reduced bias for duplex; `byp` pad to
both mixer feeds with the LNA off (fallback external LNA); `se` single-ended input; `rt` Q-spoil.
Supply-current limits in `characterize.py`: ≤ 19.0 mA (RX bias), ≤ 11.8 mA (`lobias=1`).

Bench views: `ext` = extracted; `extpr` = extracted + `pad_rf_pair` + gate resistance 150 Ω/10 µm; `extpp` =
pessimistic end (Rg 200 Ω/10 µm, +25 % device C, pad C +30 %, spiral Q 4 / L −15 %); `extlo` = optimistic end
(Rg 60 Ω/10 µm, pad C −20 %, spiral L +10 %).

<!-- RESULTS:BEGIN (rendered by summarize.py from generated/*.json) -->
## 5. Results

Extracted (parasitic C), tt / 27 °C / 3.3 V unless a range is given; ranges are min..max over the 12 corners
tt/ss/ff × 22/32 °C × 3.15/3.35 V. Only blocks with current evidence are listed (section 1).

### Physical and four-test status

| Block | Area (um2) | Magic DRC | KLayout DRC | LVS | safe | clean | observable | fallback |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| bbfilter_i | 341901 | 0 | 0 | unique match | pass | pass | pass | pass |
| bbfilter_q | 341901 | 0 | 0 | unique match | pass | pass | pass | pass |
| bb_tap | 19511 | 0 | 0 | unique match | pass | pass | pass | pass |

### bbfilter_i (bbfilter_q is the same cell; `generated/bbfilter_[iq]-evidence.json`)

| Metric | Target | Extracted |
| --- | --- | --- |
| −3 dB cutoff at reset codes (cap 8, Q 6) | trimmed per part | 13.75 MHz (10.25..19.52 MHz) |
| −3 dB cutoff, narrowest (bw = 15) | 100 kHz | 1.56 MHz (miss) |
| passband peaking at reset codes | ≤ 1 dB | 0.63 dB |
| PGA range | −6..42 dB, 3 dB steps | −6.15..41.6 dB |
| Wi-Fi 20 MHz trim (CNV-01): f3 = 10.5 ± 0.5 MHz, droop ≤ 3 dB at 8.75 MHz, ≥ 38 dB at 31.25 MHz, peaking ≤ 1 dB, at every PGA code | pass at 12 corners × 17 codes | pass; cap code 8..20, Q code 6 with a per-PGA-code offset |
| wide range (GX-1): f3 in 20..30 MHz, peaking ≤ 1 dB, droop ≤ 3 dB at 19.1 MHz | pass at 12 corners | pass; cap code 0..3, Q code per coarse PGA state |
| supply current, RX active | allocation 3.77 mA | 5.22 mA (4.99..5.32) (miss) |
| output CM − input CM, input CM 1.75 V, PGA 0 / 42 dB | ≤ 50 mV | −0.34 mV |
| DC operating point and power-up ramp at PGA 42 dB (5 corners): unique solution from 4 extreme starts, no latch | pass | pass |
| stability: kick + input-CM step at skewed corners, 40 code combinations | residual < 50 µV or decaying | pass |
| fine DC-offset DAC | LSB < 1 mV, range > ±80 mV, monotonic | LSB 0.33..0.47 mV, ±120 mV, DNL −0.12..+0.34 LSB |
| input-referred noise at 5 MHz, PGA 0 / 12 / 42 dB (tt) | — | 101 / 30.4 / 15.8 nV/√Hz |
| TX direction (`tx_in` → `out_tx`) | — | gain −0.20 dB, f3 13.75 MHz |
| TX → RX direction switch settling to 1 % | 1 µs | 0.15 µs |
| filter off: `rx_in` → `out_rx` isolation | — | −52.1 dB |
| island off, ADC node driven to 1.65 / 3.63 V: current into `out_rx` (the `island_off` clamp) | — | 53..77 µA |
| bench self-tests (ideal Butterworth, 4kTR noise, latch and oscillation detectors must fail broken cases) | all pass | pass |

### bb_tap (`generated/bb_tap-evidence.json`)

| Metric | Target | Extracted |
| --- | --- | --- |
| observe gain, in → pad, 10 pF ∥ 100 kΩ | ~0 dB | −1.37 dB (−1.49..−1.29) |
| observe −3 dB bandwidth into 10 pF | ≥ 20 MHz | 71.3 MHz (64.0..77.4) |
| pad common mode in observe | — | 0.82 V (0.70..0.93) |
| inject gain, pad → chain node | — | −0.10 dB |
| supply current observing | — | 1.01 mA (1.00..1.03) |
| TX observe through `bb_tap` (bbfilter evidence): gain / HD3 at 0.4 and 0.8 Vpk diff | — | −1.57 dB / −69.4 and −41.7 dBc |
| pad current, tap off or island off, pad at 3.63 V, 0..85 °C | — | ≤ 0.24 nA |
| capacitance added to one pad when off | — | 93 fF |

<!-- RESULTS:END -->

## 6. Open items

1. **LNA redesign open, review NO-GO** (`scratch/review-lna3/REPORT.md`, state in `scratch/rf-lna-p/NOTES.md`;
   RFR-11..14). On-chip source degeneration is adopted and the source pads are withdrawn. Not closed:
   common-mode input resistance is negative with supply-bond inductance; differential stability margin fails at
   ff with the present gate resistors; pessimistic-corner chain NF is far above the 4.1 dB on-chip target
   (tank Q).
2. **LNA input match.** The board network the benches assume (`lna_match.BOARD_TRIM`, B18/B25) cannot be built
   on the COB (no signal passives on the COB; nearest part is on the carrier). The match on the real package
   channel is not done (RFR-13).
3. **Fallback external LNA** (allowed off-chip item, `byp` path): input impedance, gain plan and NF not simulated.
4. **LNA ground.** `AGND_RX` must be planned on standard bond fingers; the fixed 74-wire bond layout has no
   down-bonds or extra openings. The mixer `VSS` is bound to `VSS` at the top while the LNA uses `AGND_RX`
   (`integration/top/decisions.md` D-LNA).
5. **Spiral cells.** `pt_lna_ind` exists as a DRC-only GDS without an LVS netlist; `pt_lna_deg` has a generator
   and model only. Both are `demand` masters in `integration/top/masters.txt`. Fill keep-out over the spirals
   is not defined.
6. **Mixers with the real LO.** As published, `pt_lo_ext` into the extracted mixers loses 3.3 dB at tt and
   9.8 dB at ss/32 °C/3.15 V against the ideal square LO used here (`analog/timing/README.md`, MW-20). Chain
   gain and NF must be restated with the real LO levels.
7. **Stale records.** `generated/lna-evidence.json`, `rf_rx_chain.json`, `rf_rx_linearity.json` and
   `rf_rx-summary.json` describe earlier LNA/mixer cells. `rxmix_*-evidence.json` matches the current netlist
   but an earlier layout (GDS hash differs). The filter's chain-NF penalty row uses a pinned chain reference
   from an earlier LNA; only its filter-alone noise is quoted above (MOD-05).
8. **Uncommitted work.** `lna.spice`, `rxmix_*.spice`, `bb_tap.spice`, the Python sources and their
   `generated/` records differ from git; `lna_layout.py`, `lna_spiral.py`, `lna_match.py` and
   `bench_selftest.py` are untracked. The canonical `run_rf_rx.sh` has not been run on this tree.
9. **bbfilter.** Current 5.22 mA against the 3.77 mA allocation (PWR-08); narrowest cutoff 1.56 MHz, so LoRa
   203/406 kHz channels need a lower cutoff; calibration routine (inject → observe) not modelled; area repack
   not started; no Monte Carlo (RFR-02, CNV-01).
10. **DC offset.** TIA offset DAC and filter fine DAC are FPGA-calibrated; residual and dynamic offset against
    ADC full scale at high PGA gain is open (RXR-02).
11. **Not covered in any bench:** wire and via resistance (C-only extraction), supply and substrate coupling,
    IIP2, LO leakage to the antenna port, corners for linearity (RFR-05, RFR-07).
12. **Analog nets crossing islands without isolation** (`DAC*`, `ADC*`, `BB*_OBS/INJ`): rule or clamp to be
    agreed (`integration/top/decisions.md` D-ANA).
