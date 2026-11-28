# R+C evidence audit, 2026-11-28 (both chips, RF TX blocks excluded)

Trigger: RFT-07. rfdriver published 7.1 dBm from a C-only netlist and gets −10.7 dBm with full R+C. This audit asks
the same question of every other analog or custom block: what view did its performance evidence use?

Rerun versus read. The inventory (table 1) was **read** from block records, READMEs, bench scripts and scratch.
Table 2 was **rerun**: seven blocks, extracted and benched here.

## Method (rerun blocks)

- **Extraction.** `scratch/reviews/rc_audit/rcx.py` runs two Magic extractions on one flattened copy of the
  published GDS: a C-only reference, and full-coverage extresist (tolerance 0.001, simplify off, **supplies
  resisted**, only VSUBS ignored). It then applies the MANDATE 4a C repair (`converters/rcext.py` fixcap): ground C
  per net is rebuilt from the C-only run, and dropped coupling pairs are restored.
  - Every `x/<block>/rcx.json` reports coverage and a per-net ground-C cross-check. The max relative error is 0 on
    every block.
  - The nets left without R are poly-resistor internal nodes, MIM terminals and short gate stubs, except as noted
    in table 2.
- **Image.** The pinned canary image (`librelane-gf180-canary:2026.08`) is not on this machine. Magic 8.3.678 from
  the analog/KLayout image `sha256:bd7a702b…` was used instead (the same one rf_tx `RFTX_IMAGE` uses).
- **Benches.** Each block's existing bench was run unchanged, once on the published C-only netlist and once on the
  R+C netlist (drivers `wrx_rc.py`, `rfrx_rc.py`, `lovreg_rc.py`, plus `pll_vreg2_ext.py` through
  `PLL_VREG2_EXT`). All runs are tt / 27 C / 3.3 V unless noted, one at a time, at most 2 jobs.
  - Known-answer check: the C-only runs reproduce the published figures. lo_vreg gave 45.9 / 47.4 dB, equal to
    `ext_table.json`; rxmix_i gave 24.43 dB, equal to its evidence record.
- **Hand R cross-check (termination `TERM_VCM`).**
  - The pin strap is Metal5, 0.44 µm × 318 µm (read from the GDS with KLayout). At 40 mΩ/sq that is 29 Ω end to
    end. Extracted: 17–38 Ω along the trunk from the pin to the switch drains, plus ~18 Ω per drain tap
    (single-cut stack: contact 6.3 + vias 4.5 Ω each). This agrees.
  - Second check (pll_vreg2 `VOUT_CDR`): the visible Metal4 strap (4 × 378 µm) gives 8.5 Ω, but the extracted path
    has a 20.8 Ω segment. That disagreement is **not resolved**; see TIM-38.

## Table 1: evidence view per block (read)

Views:
- **sch**: schematic only.
- **C**: C-only extraction.
- **R+C sig**: resistance on signal nets only (ideal supplies).
- **R+C both**: resistance on signal and supply nets.

Risk is the R-sensitivity rating, as briefed.

| Block | Chip | Key spec | Evidence view | Supply current | R risk |
|---|---|---|---|---|---|
| pt_lna | rf | NF ≤ 6, S11 ≤ −10 dB, IDD ≤ 19 mA | R+C both, 11 current nets only (mesh solver, `lna.rext.spice`); rest C | 15.1 mA | high (partly covered) |
| pt_lna_ind / pt_lna_deg | rf | – | analytic model only | – | high (no extraction) |
| pt_rxmix_i/q | rf | gain > 0, IDD ≤ 6.11 mA, offset after cal < 10 mV | C (+ gate R in chain views) | 5.0 mA | high → **rerun** |
| pt_bbfilter_i/q | rf | f3, peaking ≤ 1 dB, 3.77 mA allocation | C | 5.2 mA | medium |
| pt_bb_tap | rf | gain ~0 dB, BW ≥ 20 MHz | C | 1.0 mA | medium |
| pt_adc_i/q | rf | ENOB/SFDR at 40 MS/s | R+C sig (rcext.py, VDD/VSS ideal); four-test C | 5.7 mA | high (supplies open) |
| pt_dac_i/q | rf | FS ±1 V, ≤ 4 LSB | R+C sig, static only | 1.9 mA | medium |
| pt_refbuf | rf | VREF 1.0 V, settling | C | 0.55 mA | high (low-Z reference) |
| pt_refvcm | both | VCM/VDD ≈ 0.5 | C | 15–29 µA | low |
| pt_core_bias_rf/_wired | rf / wired | 7.5–12.2 µA, VBG 1.19–1.23 V | C, trunk wire R not modelled | µA | medium (long trunks) |
| isw_* | both | drop ≤ 20 mV at 30–80 mA | drop: R+C both (`.pexrc`); soft start: C | 30–80 mA | covered (drop) |
| iso_clamp, atb_* | both | function, Ron | C | – | low |
| por | both | one release | R+C both (extresist tol 10) | µA | low |
| pt_char_* | both | ring/CML speed | C + gate R | 0.5–5 mA | low (characterisation) |
| pt_pll_ring | both | lock 480–810 MHz | R+C sig (`pll_ring.rc.spice`); nominal rows C | 5.3–8.5 mA | high (supplies open) |
| pt_pll_ring_core | both | as pll_ring | none (DRC/LVS only) | – | high (no evidence) |
| pt_pll_vreg2 | both | rejection ≥ 20 dB 10–200 MHz, DJ < 5 ps | C | 3–8 mA load | high → **rerun, FAIL** |
| pt_clockmux | both | 1 GHz pass/stop | C | 0.3–1.6 mA | medium |
| pt_prescale | both | 2.5 GHz /16 | C, tt only | 2.0 mA | high |
| pt_wordclk | wired | /5 /10 /20 at 810 MHz | C | 1.2–2.4 mA | medium |
| pt_lo_ext | rf | mixer gain vs square LO | C + bench Rg | 11.1 mA | high |
| pt_lc_qvco5 | rf | range, I/Q 80–100° | R+C sig (core), loads mixed | 16.6–19.3 mA | high (supplies open) |
| pt_lo_mmd | rf | divides to QVCO top + 5 % | R+C sig; fails ss | 18–36 mA | high (supplies open) |
| pt_lo_mmd_qdum, pt_lo_obs, pt_obs_pre4 | rf | balance / division | C | ≤ 6.7 mA | medium |
| pt_lo_vtdet, pt_lo_lf, pt_lo_pfdcp | rf | trip / lock / CP current | sch / behavioural / C | µA | low |
| pt_lo_vreg | rf | LO-11: ≥ 33 dB at 78.125 MHz, ≥ 22 dB at 156.25 MHz | C (hierarchical + hand Rg, 0.5 Ω VIN) | 25–30 mA load | high → **rerun** |
| pt_clk_obs16, pt_diff_clk_rx, pt_ring_osc, pt_vco_replica, pt_aosc | both | frequency / division | C | 0.4–9 mA | medium (diff_clk_rx long route: TIM-08) |
| pt_cdr | both | output current change < 15 %, offset < 0.25 | C | 0.22 mA | medium |
| pt_ctle | wired | gain / peaking per code, BW | C | 4.9 mA | high → **rerun** |
| pt_termination | wired | ground switch ≪ 45 Ω (bench < 3 Ω), TERM_VCM 1.2 V | C | 1.25 mA (17.8 mA switch) | high → **rerun, FAIL** |
| pt_detect | wired | squelch / disconnect thresholds | C | 2.2 mA | high → **rerun** |
| pt_slicer | wired | 0 errors at 3.24 Gb/s, offset ≤ 10 mV | C | 6–9 mA | high (not rerun) |
| pt_wrx_cap | wired | 0/200 errors | C | – | medium |
| pt_ptrim | wired | chain 0/112 | R+C sig | – | medium |
| pt_rxlevel, pt_rxselect, pt_wmon_sel, pt_vthdac | wired | BW / settling | C | ≤ 0.5 mA | low–medium |
| pt_wiredtx8 | wired | swing, jitter per standard | no published result; s16 R+C sig sanity run only | 52–53 mA | high (not rerun: heavy, needs supply-R re-extraction) |
| pt_usb_txdrv | wired | HS 360–440 mV | C | 1.2 mA | medium |
| wtx8_casbias, pt_wtx_hsbias, pt_txpad_bias | wired | pump / bias | C (hsbias evidence hash stale) | µA | low |
| tx_interlock, tx_steer, term_buffer | wired | lifecycle, loaded current | C (pad R+C crashes Magic) | 21–32 mA | high (not rerun) |
| pt_wtx_fallback_control | wired | digital vectors | C, not live-bound | – | low |

Summary: no block in the audited set has R+C evidence on its supply nets, except the LNA (11 nets), isw (drop
only) and por. The masters in `integration/chips/masters.txt` point at the C-only views for LNA, isw and por, and
at the schematic for pt_wiredtx8.

## Table 2: R+C reruns (alternating chips)

| Block (chip) | Metric | C-only | R+C | Limit | Verdict |
|---|---|---|---|---|---|
| pt_termination (wired) | USB HS ground switch Ron | 1.98 Ω | **51.5 Ω** | < 3 Ω bench, ≪ 45 Ω | **FAIL** (WRX-24) |
| | TERM_VCM divider; supply | 1.225 V; 1.25 mA | 1.229 V; 1.17 mA | 1.2 ± 0.1 V | pass |
| pt_lo_vreg (rf) | rejection 78.125 MHz, tt t6 / ss t1 | 45.9 / 47.4 dB | 34.2 / 35.8 dB | ≥ 33 dB | pass, margin 1.2 dB |
| | rejection 156.25 MHz | 39.2 / 39.7 dB | 25.1 / 26.5 dB | ≥ 22 dB | pass, margin 3 dB |
| | 1 GHz; VOUT | 39 dB; 2.697 V | 8.6 dB; 2.673 V | – | degraded |
| pt_ctle (wired) | peak gain, code 3 | 3.97 dB | 0.45 dB | – | degraded (all codes −2.5 to −3.6 dB) |
| | peaking, code 3 / BW code 7 / bypass BW | 6.44 dB / 12.8 GHz / 2.46 GHz | 4.37 dB / 9.4 GHz / 1.69 GHz | bench flags | bench pass; chain rows must be rerun |
| pt_rxmix_i (rf) | conversion gain: ideal LO / real LO tt / ss | 24.4 / 21.5 / 19.4 dB | 21.3 / 20.2 / 18.8 dB | > 0 | pass |
| | supply current RX | 5.04 mA | **3.42 mA (−32 %)** | ≤ 6.11 | pass, but the bias point moves; chain NF/IIP3 unverified |
| | raw TIA offset | 14 mV | 68 mV | < 10 mV after calibration | calibration range not rerun |
| pt_detect (wired) | all squelch / disconnect / FS / rx-detect cases | pass | pass | bench | pass; vref 0.497 → 0.540 V (+8.6 %), disconnect at CM 500 mV hit fraction 1.0 → 0.72 |
| pt_pll_vreg2 (both) | CDR VOUT at the ring load | 2.858 V | **2.648 V** | – | IR drop 210 mV |
| | rejection at 78 MHz (tran), ring DJ at 625 MHz, spur | 22.6 dB, 4.0 ps, −42 dBc | **7.5 dB, 26.4 ps, −26 dBc** | ≥ 20 dB, < 5 ps | **FAIL** (TIM-38) |

The pll_vreg2 C-only run uses the current `pll_ring.ext.spice` as its load, so it differs slightly from the
published record (f0 1014 vs 936 MHz). Both views used the same load.

Extraction notes:
- **lo_vreg.** Coverage is 26 of 134 routed nets. VIN, VOUT, VSS and the pass drain are fully resisted (93 k
  resistors). XCTL.G2 (1.47 pF, the pass gate) carries no R.
- **pll_vreg2.** INP and NB carry no R.
- **rxmix_i.** XX7_cz, XX8_cz and vbpf are capacitor plates.

## Not rerun (high risk, open)

- **wired:** pt_slicer, pt_wiredtx8 (needs supply-resisted re-extraction of the 52 mA serializer; its s16
  infrastructure ignores VDD/VSS), and the pad lifecycle cells (Magic crash).
- **rf:** pt_bbfilter, pt_lo_ext, pt_lo_mmd and pt_lc_qvco5 supply R, pt_prescale, pt_refbuf, and the ADC supplies.

## Files

- Scripts: `scratch/reviews/rc_audit/{rcx.py, netr.py, wrx_rc.py, rfrx_rc.py, lovreg_rc.py}`.
- Small results committed: `scratch/reviews/rc_audit/results/`. Netlists stay in the untracked `x/`.
