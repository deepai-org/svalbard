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
| `lna` | `pt_lna` | candidate, not published (stability closed in the active range; noise figure misses) | 60,752 (253.05 × 240.08), plus two 57.2k tank and two 25.2k degeneration spirals | 0 / 0, unique; read-back from GDS unique | `generated/lna-evidence.json` (current, `lna_close.py`) |

Areas and DRC/LVS are from `generated/<block>-layout.json`. `integration/top/pt_chip.conn` binds the cells in
`generated/` (masters `generated/<block>.ext.spice`), including the candidate LNA and mixer pin lists. The
The netlists and layout records of all blocks in git match the cells on disk; `pt_lna` has two new pins (`tail`, `vtk`).

## 2. Files and how to run

| File | Content |
| --- | --- |
| `netlists.py` | writes every `<block>.spice` (single source of the circuits; top cell `pt_<block>`) |
| `bbf_fd.py`, `bbf_layout.py`, `bbf_bench.py` | baseband filter circuit, layout and benches (with bench self-tests) |
| `lna_layout.py`, `lna_spiral.py`, `lna_match.py` | compact LNA/mixer layout, spiral cells and models, stability bench, real-channel ladder and per-chip match fit |
| `lna_close.py` | LNA closing evidence: currents (20 corners), stability matrix, band rows on the real channel, negative controls → `generated/lna-evidence.json` |
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
`scratch/rf_rx/` (gitignored). Do not run `run_rf_rx.sh` or `summarize.py` yet (Open item 8); the LNA evidence
comes from `python3 lna_close.py currents|stab|band|neg|write`.

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

LC-tuned transconductance stage, true differential:

- Common-source pair 450/0.28 per side, ~12 Ω series gate resistors, AC-coupled from the pads (47 µm MIM). The sources go
  through the on-chip degeneration spirals (`pt_lna_deg`, 0.47 nH each, 25 Ω ppoly in parallel with each spiral) to the
  common pin `tail`: a cascoded NMOS tail current source, mirrored from `ibias` (no replica bias; `lobias` switches extra
  reference width in). Gate common mode from a replica diode on a level resistor.
- One cascode (300/0.28, 64 units) per leg into `tank_p/n`; current-steering attenuator `att[4:0]` + `gain_lo` (MSB):
  units are steered to the tank or dumped onto `vtk` (cascode gates switched by PMOS pass devices).
- Tank: two `pt_lna_ind` spirals (220 µm, 4 turns, 2.01 nH) from the centre tap `vtk` to `tank_p/n`; `vtk` is fed from
  `VDD` through an always-on PMOS (~12 Ω) and returned to `VSS` by a 19 pF NMOS gate capacitor, so the load current
  closes on chip and not through the supply bonds. `ct[3:0]` tank tune, 0.05 pF per leg per LSB.
- 16 µm MIM from each tank node to each mixer (`rf_out_*` → rxmix_i, `rf_outq_*` → rxmix_q), 20 kΩ across each pair.
- Common-mode loss network: 0.1 pF from each RF pad to one node, 200 Ω from there to `VSS` (differential: only pad
  capacitance).
- `byp`: pad to both mixer feeds through a series MIM with the LNA off (fallback external LNA); `se` single-ended
  input; `rt` Q-spoil.

Why the stage looks like this (common-mode stability, RFR-14): in a pseudo-differential stage the common-mode drain
current returns through the supply and ground bonds; above the resonance of the bond loop with the on-chip
VDD–VSS capacitance the chip ground moves against the board like a capacitive source impedance and the
common-mode input resistance goes negative (−57 Ω at 1.1 GHz on the previous cell). The tail removes the
common-mode current, the local return keeps what is left on chip, and the loss network outweighs the remaining
tail-capacitance term. The 25 Ω across each degeneration spiral damps the spiral / source-capacitance resonance
near 13 GHz, which is where the differential input resistance used to go negative.

Supply-current limits: ≤ 19.0 mA (RX bias), ≤ 11.8 mA (`lobias=1`), at every corner. Evidence script:
`lna_close.py` (limits are constants in the file) → `generated/lna-evidence.json`.

Bench views: `ext` = extracted (capacitance only); `extpr` = extracted + `pad_rf_pair` delta + gate resistance
150 Ω/10 µm; `extpp` = pessimistic end (Rg 200 Ω/10 µm, +25 % device C, pad C +30 %, spiral Q 4 / L −15 %); `extlo`
= low-loss end (Rg 60 Ω/10 µm, pad C −20 %, spiral L +10 %). Input network in the band and chain rows: the real COB
channel (`lna_match.channel_ladder`: bond 2.45 nH, 5.5 mm of 86.6 Ω trace, via, connector, carrier line) with lossy
carrier parts fitted per chip.

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

## 5a. LNA candidate: results against the limits (`generated/lna-evidence.json`, written by `lna_close.py`)

Extracted (capacitance only), 20 corners = tt / ss / ff / sf / fs × 22 / 32 °C × 3.15 / 3.35 V unless stated. Limits were
fixed before the runs. Rows marked **miss** are misses; nothing here is published.

| Row | Limit | Result | State |
| --- | --- | --- | --- |
| Area; Magic / KLayout DRC; LVS; read-back LVS from the GDS | 0 / 0, unique | 60,752 µm²; 0 / 0; unique; unique (981 devices), negative control fails as required | pass |
| Supply current, RX bias / `lobias` | ≤ 19.0 / ≤ 11.8 mA at every corner | 17.75–18.62 / 10.80–11.44 mA; off 1–7 nA | pass |
| Two-port stability, 56 rows (corners, model ends, states, supply cases), 0.1–30 GHz | μ > 1, K > 1 | μ ≥ 1.008, K ≥ 2.94 | pass |
| Differential min Re(Zin), real mixers, 0.1–30 GHz | ≥ 1.0 Ω | 0.975–1.29 Ω, every minimum at 30 GHz (disabled LNA: 0.83 Ω); ≥ 2.5 Ω below 8 GHz; 25 rows below 1.0 | **miss** |
| Common-mode min Re(Zcm), 0.1–30 GHz, physical supply cases | ≥ 1.0 Ω | 0.43–0.58 Ω at 30 GHz (disabled LNA: 0.39 Ω); below 8 GHz ≥ 1.4 Ω with the real supply network, 0.68 Ω with 2 nH bonds and no decap; duplex bias with the real network 0.74–0.88 Ω in band (review 4) | **miss** |
| Same, undamped 100 / 500 pF on the island rail, no die decap | ≥ 1.0 Ω | −3.8 to −29.5 Ω at 0.16–0.34 GHz | **miss** (rule RQ-3) |
| Same from 5 MHz, real supply network (anti-resonance with the die decap) | ≥ 1.0 Ω | 3 nF / 0.03 Ω / 1–2 nH per rail at ff: −0.74 / −9.8 Ω at 66 / 47 MHz; ≥ 2.1 Ω with 5.4 nF and ≤ 0.5 nH, with 0.1 Ω of decap loss, at tt, ss and in duplex bias | **miss** (RQ-3a) |
| Pads owner's coupled bond model (RX pair, ground and supply bonds with all mutuals, 0.25 Ω per wire), site options A / B × min / nom / max, ff, 24 rows incl. 5 MHz–1 GHz | same limits | μ ≥ 1.012, K ≥ 7.1, differential ≥ 1.50 Ω, common mode ≥ 2.98 Ω from 5 MHz to 1 GHz; 0.55–0.59 Ω at 30 GHz (passive) | pass / **miss** above 9 GHz |
| Die-VSS bounce to differential input at 2421.875 MHz (bond coupling; information) | — | RX on bonds 69/70: −17.9 dB (−19.9…−17.7); on 67/68: −40.3 dB with die decap (−43.7…−37.5), −29 dB without | information (RQ-5) |
| RF pad capacitance tolerance | — | per +0.1 pF per leg: NF +0.15 dB, gain −0.27 dB; S11 ≤ −10 dB lost above about +0.4 pF | information |
| Negative controls | bench must fail | broken LNA (tail shorted, feed on VDD, CM network shorted): −25.5 Ω; bench self-tests all as required | pass |
| S11 on the real channel, carrier parts at connector + 2 mm, fitted per chip | ≤ −10 dB, 2.395–2.4885 GHz | −10.8 to −11.7 dB; at 10 mm −9.9 dB | pass / **miss** at 10 mm |
| LNA gain, source EMF to mixer feeds (50 Ω per leg model), real channel | — | tt 0.5–0.8 dB (ideal lossless match 3.3 dB); ss −1.2…−0.3; ff 1.4–2.1; pessimistic end −6.2…−5.9 dB | information |
| LNA NF including the real channel (2.4–2.7 dB of loss before the LNA) | ≤ 6.0 dB; pessimistic end derated +1.5 dB | tt 3.6–3.9; ss 4.0–4.4; ff 3.3–3.6; sf 3.8–4.1; fs 3.4–3.8 dB; pessimistic end 5.3–5.6 dB (7.1 derated) | pass / **miss** at the pessimistic end |
| Chain NF, DSB, real channel, LO as delivered (sine, best real level), small TIA | ≤ 4.1 dB | tt, LO ±0.37 V: 6.15 dB (LNA + channel 3.9 dB, TIA terms +2.3 dB), gain 31.2 dB; ss 32 °C 3.15 V, LO ±0.26 V: 8.11 dB, gain 26.0 dB; pessimistic end, LO ±0.11 V: 14.7 dB, gain 13.8 dB (weak LO: the TIA terms dominate) | **miss** |

## 6. Open items

1. **LNA noise figure misses the on-chip target (RFR-01, RFR-13).** See the LNA rows in section 5a. The pad resistance of
   the stage is 7–9 Ω (0.55 pF of pad capacitance per leg divides the gate impedance), the bond plus COB trace put about
   4.4 Ω of series loss in front of it, and no part can sit on the COB: 2.4–2.7 dB is lost before the LNA at
   connector + 2 mm, 3.8 dB at 10 mm. The small TIA (decision in force) adds about 2.5 dB at tt. Levers not used: larger
   TIA (×3: −1.5 dB, +36k µm² per mixer), lower RF pad capacitance (pads), a reworked shunt part on the COB (not allowed
   on the unmodified board), the off-chip fallback LNA.
2. **LNA stability rows that miss their limit.** (a) Above about 9 GHz both the differential and the common-mode input
   resistance fall below 1.0 Ω (0.98–1.3 Ω and 0.43–0.58 Ω at 30 GHz); the disabled LNA reads 0.83 / 0.39 Ω there, so
   this is the passive pad network, not the stage; the limit as written (0.1–30 GHz) is not met. (b) An undamped
   capacitor of 100–500 pF directly on the rf_rx island rail with no die decap behind it gives −4 to −29 Ω of
   common-mode resistance at 0.16–0.34 GHz: rule RQ-3 for the power-delivery owner.
   (c) Below 100 MHz the bond loop resonates with the die decap: at ff, with low-loss die decap (0.03 Ω) and ≥ 1 nH per
   rail, the common-mode resistance is negative in a band under 1 MHz wide at 45–100 MHz (`lna_close.py stab_lf`); in
   duplex bias with the real supply network it is 0.74–0.88 Ω in the signal band (review 4).
   Independent review 4 (reviewer scratch `scratch/review-lna4/`): NO-GO for publication in this state.
3. **LNA input match** is fitted per chip (per-board tuned carrier parts, B18/B25). One fixed BOM over part and bond
   tolerance is not shown; at 10 mm the fitted network reaches only −9.9 dB.
4. **Extraction is capacitance-only** for every block here: wire and via resistance are not in any number (gate and
   source wiring resistance adds directly to the LNA noise). No Monte Carlo.
5. **Fallback external LNA** (allowed off-chip item, `byp` path): input impedance, gain plan and NF not simulated.
6. **Spiral cells** `pt_lna_ind`, `pt_lna_deg`: DRC-clean GDS, analytic models only (no EM, no LVS netlist, no mutual
   coupling: k = ±0.1 moves the pad resistance by ∓1.3 / +1.6 Ω); fill keep-out over them is not defined (SG-3). Review 4:
   halving or removing the degeneration spirals keeps the LNA-plus-channel NF and adds 1–1.8 dB of gain (not yet scanned
   over corners). No secondary ESD clamp at the gates behind the 4.4 pF input MIMs and no HBM check of this cell. The LNA uses die `VSS` (PC-21): ground-injection gain not simulated (PD2-15).
7. **Mixers with the real LO.** As published, `pt_lo_ext` into the extracted mixers loses 3.3 dB at tt and 9.8 dB at
   ss/32 °C/3.15 V against the ideal square LO (`analog/timing/README.md`, MW-20).
8. **Stale records.** `rf_rx_chain.json`, `rf_rx_linearity.json`, `rf_rx-summary.json` and `rxmix_*-evidence.json`
   describe earlier cells; `characterize.py --blocks lna` still contains the pre-COB board network and is superseded
   for the LNA by `lna_close.py`. The filter's chain-NF penalty row uses a pinned chain reference from an earlier LNA
   (MOD-05). Do not run `run_rf_rx.sh` or `summarize.py` until `characterize.py` is brought in line.
9. **Read-back LVS note.** Three segments of the cascode-divider resistor are 8.667 µm in the netlist and 8.67 µm
   drawn; netgen matches uniquely with properties, the device census flags the 3 nm.
10. **bbfilter.** Current 5.22 mA against the 3.77 mA allocation (PWR-08); narrowest cutoff 1.56 MHz, so LoRa
    203/406 kHz channels need a lower cutoff; calibration routine (inject → observe) not modelled; area repack
    not started; no Monte Carlo (RFR-02, CNV-01).
11. **DC offset.** TIA offset DAC and filter fine DAC are FPGA-calibrated; residual and dynamic offset against
    ADC full scale at high PGA gain is open (RXR-02).
12. **Not covered in any bench:** supply and substrate coupling, IIP2, IIP3, LO leakage to the antenna port, corners
    for linearity (RFR-05, RFR-07).
13. **Analog nets crossing islands without isolation** (`DAC*`, `ADC*`, `BB*_OBS/INJ`): rule or clamp to be
    agreed (`integration/top/decisions.md` D-ANA).
