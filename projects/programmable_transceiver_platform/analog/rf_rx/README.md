# RF receive family: LNA, I/Q mixers, shared baseband filter, BB tap

Transistor-level `lna`, `rxmix_i`, `rxmix_q`, `bbfilter_i`, `bbfilter_q` (shared RX/TX filter with the PGA as its
first stage) and `bb_tap` (analog observation / injection buffer, also used for `WMON`). Numbers come from
`generated/*.json`; nothing here is silicon or Monte Carlo evidence. Exact pin lists, bindings and register
sources: `chip-top-pins.md`. Risks: IDs refer to `spec/risk-register.md`.

## 1. Status

| Block | Cell | State | Area µm² (bbox µm) | DRC Magic / KLayout, LVS | Performance evidence |
| --- | --- | --- | ---: | --- | --- |
| `bbfilter_i`, `bbfilter_q` | `pt_bbfilter_i/q` | published, committed | 341,901 (586.3 × 583.15) | 0 / 0, unique | current: matches netlist and GDS |
| `bb_tap` | `pt_bb_tap` | published on disk | 19,511 (99.08 × 196.92) | 0 / 0, unique | current: matches netlist and GDS (20 corners) |
| `rxmix_i`, `rxmix_q` | `pt_rxmix_i/q` | candidate, not published | 35,442 (192.73 × 183.9) | 0 / 0, unique | current (reduced 10-corner set); chain NF / IIP3 rows open |
| `lna` | `pt_lna` | candidate, NOT publishable: layout round 3 fixes the current-carrying routes only in part; metal-aware results miss NF, S11, chain NF and common-mode stability (5a) | 129,592 (round 3; was 64,712), plus two 57.2k tank and two 14.0k degeneration spirals | 0 / 0, unique | section 5a (`scratch/rf_rx/close_rext/`, `scratch/rf_rx/r3/`) |

Areas and DRC/LVS are from `generated/<block>-layout.json`. `integration/chips/{rf,wired}/chip.conn` binds the cells in
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
comes from `python3 lna_close.py stab_b|stab|stab_lf|currents|band|chain|startup|pkg|neg|write`.

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
  through the on-chip degeneration spirals (`pt_lna_deg`, 100 µm, 0.31 nH each, 25 Ω ppoly in parallel with each spiral) to the
  common pin `tail`: a cascoded NMOS tail current source, mirrored from `ibias` (no replica bias; `lobias` switches extra
  reference width in). Gate common mode from a replica diode on a level resistor, filtered by 60 kΩ and a 4 pF MOS
  capacitor (0.7 MHz): supply ripple on the replica otherwise carries the 45–100 MHz supply anti-resonance into the
  common mode.
- One cascode (300/0.28, 64 units) per leg into `tank_p/n`; current-steering attenuator `att[4:0]` + `gain_lo` (MSB):
  units are steered to the tank or dumped onto `vtk` (cascode gates switched by PMOS pass devices).
- Tank: two `pt_lna_ind` spirals (220 µm, 4 turns, 2.01 nH) from the centre tap `vtk` to `tank_p/n`; `vtk` is fed from
  `VDD` through an always-on PMOS (~12 Ω) and returned to `VSS` by a 10 pF `nfet_06v0` gate capacitor, so the load current
  closes on chip and not through the supply bonds. `ct[3:0]` tank tune, 0.05 pF per leg per LSB.
- Secondary ESD clamps behind the pad MIMs: an off PMOS (junction to `VDD`) and an off NMOS (junction to `VSS`), 4 µm each,
  at both gate nodes and both bypass nodes.
- 16 µm MIM from each tank node to each mixer (`rf_out_*` → rxmix_i, `rf_outq_*` → rxmix_q), 20 kΩ across each pair.
- Common-mode loss network: 0.27 pF from each RF pad to one node, 95 Ω from there to `VSS` (differential: only pad
  capacitance, which costs 0.15 dB of NF per 0.1 pF).
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

## 5a. LNA candidate (round 3 layout, 2026-11-19): results against the limits

Views: `ext` = C-only extraction; `rext` = `generated/lna.rext.spice`: C-only plus the solved metal networks of the current-carrying
nets (`lna_netres.py`, pads owner's mesh solver), cross-checked by Magic `extresist simplify off` on all nets (15.4 vs 15.2 mA).
`rext` is the evidence view. Bond / ground model: pt_rf map (`pkg_rf.py`, `generated/pkg-rf-bond-model.spice`). Limits unchanged.

| Row | Limit | Result | State |
| --- | --- | --- | --- |
| Layout | DRC 0 / 0, LVS unique | 129,592 µm²; 0 / 0; unique (read-back LVS not redone) | pass (area +64.9k) |
| Supply current, RX / `lobias`, 20 corners, rext | ≤ 19.0 / ≤ 11.8 mA | 14.5–15.5 / 9.9–10.3 mA (C-only 18.2: metal drops on VSS / tail cost 16 %) | pass, below design point |
| Electromigration of the stage-current routes (85 °C, 2.09 mA/µm, 0.58 mA/cut) | pass | tracks ≤ 2.07 mA/µm, ≤ 0.46 mA per cut (mesh solver) | pass (old layout ~30× over) |
| Stability, pt_rf bond model × 3 bounds, 38 rows + references, 5 MHz–30 GHz, rext | μ, K > 1; Re ≥ 1.0 Ω | μ ≥ 1.008, K ≥ 2.95, differential ≥ 1.17 Ω; common mode 0.74–1.34 Ω at 5–8 GHz (LNA off 0.90), 0.45 Ω at 30 GHz; ≥ 1.07 Ω below 1 GHz | **miss** (common mode) |
| Same, old map vs pt_rf map (same bench) | — | identical within 0.01 Ω: the ground inductance is not the lever | information |
| S11, real channel, per-chip carrier fit, rext | ≤ −10 dB | tt −9.69, ff −9.07, ss −10.10, pessimistic −10.43 dB | **miss** |
| LNA NF incl. channel, rext | ≤ 6.0 dB (pessimistic +1.5) | tt 4.8–5.1, ff 4.3–4.6, ss 5.5–5.8, pessimistic 7.2–7.4 (8.9 derated) dB; gain tt −3.3…−2.6 dB | pass / **miss** pessimistic |
| Chain NF DSB, real channel, LO as delivered, small TIA, rext | ≤ 4.1 dB | tt 6.26 (31.0 dB), ss 7.80 (26.1 dB), pessimistic 15.2 dB (11.6 dB) | **miss** |
| Fallback: external LNA (15 dB, NF 1 dB, 2.5 dB before, 0.8 dB balun) in front of the active LNA; Friis on the chain rows | system 8 dB | tt 3.9, ss 4.1, pessimistic 6.5 dB (20 dB gain: 3.6 / 3.7 / 4.7) | pass (cascade, not a joint simulation) |
| Die-VSS bounce → differential input at 2421.875 MHz, through the LNA, 5.4 nF decap | — | pt_rf map −38.4 / −44.1 / −59.7 dB (min / nom / max; old map −47.2 nom); with the D2H-dominated bounce rescaled to the pt_rf ground (0.25 / 2.5 / 12.5 mV rms): about −91 / −83 / −90 dBm against −100 dBm | **miss** (PD2-15) |
| IIP3, Monte Carlo | ≥ −10 dBm | not run on this layout (last: −11.0 dBm, tt, ideal match, previous layout) | open |

Remaining metal resistance (mesh solver, typ): source 7.1 / 8.2 Ω, tank 8.7–13.6 Ω, cascode node 7–12 Ω, tailx 4.7 Ω, VDD / VSS 1.8 /
1.6 Ω. The generic row router puts the trunks outside the device rows; a placement-level LNA layout (heavy devices adjacent,
local trunks, Kelvin bias reference) is the next step and is expected to recover most of the 0.8 dB NF / 2.9 dB gain that `rext`
loses against `ext`.

## 6. Open items

1. **LNA noise figure misses the on-chip target (RFR-01, RFR-13;** `scratch/reviews/physical-limits.md` **RX-CHLOSS).**
   Pad resistance 5–7 Ω behind about 4.5 Ω of bond and trace loss, no part possible on the COB: 3.0–3.5 dB is lost before
   the LNA. The path that meets the 8 dB system figure is an external LNA in front of the ACTIVE on-chip LNA (estimate
   3.9–6.2 dB system NF with 15 dB of external gain, from the chain rows). The bypass path (`byp`, LNA off) does NOT meet
   it: 18 dB of loss from the pads to the mixers, about 20 dB system NF with a 15 dB external LNA (helper run, previous
   layout); it is a rescue path for a dead LNA only.
2. **LNA stability rows that miss their limit.** (a) Above about 9 GHz the resistances sit on the passive pad network and
   are below 1.0 Ω (kept as a miss); with the bench sources referenced to die VSS (review 5) the common mode is already
   0.78–0.99 Ω from about 5 GHz, where the disabled LNA still reads above 1 Ω. (b) With lossless lumped rails the supply anti-resonance (45–100 MHz) and an undamped
   island decap still give negative common-mode resistance; with the pads owner's coupled model every row is ≥ 2.1 Ω
   below 1 GHz. Supply rules RQ-3 / RQ-3a are requirements on power delivery.
3. **S11 at ff is −9.94 dB**, IIP3 −11.0 dBm (tt, ideal match), pessimistic-end LNA NF 5.5–5.8 dB: see 5a. The match is
   fitted per chip (per-board tuned carrier parts, B18/B25); one fixed BOM over tolerance is not shown.
4. **LNA layout: metal resistance of the stage-current routes** (5a). The earlier DC-point error of the R+C netlist was a real
   layout defect (stage current through 0.3 µm Metal2 and single PCell escapes; 4.2 mA instead of 18.3 on the old GDS with all nets
   extracted). Round 3 widened the routes (EM now passes) but source / tank / cascode routes still have 5–14 Ω: a placement-level
   layout is needed. Use `extresist simplify off` (the default writes resistance on a subset of nets) and only its resistors.
   No Monte Carlo; IIP3 not rerun.
5. **External-LO leak into the RX pair at site B** (fallback LO only; computed from the pads owner's mutuals, 1 Vpp
   differential drive): −60.5 dBm in the pads owner's convention, −55.2 dBm into the matched port against −57 dBm
   (−65.8 / −47.8 at the bounds); 17 / 58 / 135 mV of static offset at the TIA output against a ±144 mV offset DAC.
6. **Spiral cells** `pt_lna_ind`, `pt_lna_deg`: DRC-clean GDS, analytic models only (no EM, no LVS netlist, no mutual
   coupling); fill keep-out over them is not defined (SG-3). Removing the degeneration spirals altogether was scanned over
   corners: +2 dB gain, same NF, stable, but S11 −8.9…−9.9 dB; they were halved instead (2 × 14.0k µm²).
7. **Mixers with the real LO.** `pt_lo_ext` into the extracted mixers loses 1.9 dB at tt and 3.9 dB at ss/32 °C/3.15 V
   against the ideal square LO at the levels used here (MW-20).
8. **Records.** `rxmix_*`, `bb_tap`, `rf_rx_chain.json` and the summary are regenerated from the cells on disk (mixers on
   a reduced 10-corner set); `rf_rx_linearity.json` is stale. `run_rf_rx.sh` is evidence-only by default; section 5 above
   is not re-rendered (`summarize.py --readme`).
9. **LNA warm-up** is about 8 µs after `en` (gate-bias filter). The tank-return capacitor (10 pF) is on 6 V devices; the
   always-on feed PMOS and the cascode see the full rail whenever the island is on.
10. **bbfilter.** Current 5.22 mA against the 3.77 mA allocation (PWR-08); narrowest cutoff 1.56 MHz, so LoRa
    203/406 kHz channels need a lower cutoff; calibration routine (inject → observe) not modelled; area repack
    not started; no Monte Carlo (RFR-02, CNV-01).
11. **DC offset.** TIA offset DAC and filter fine DAC are FPGA-calibrated; residual and dynamic offset against
    ADC full scale at high PGA gain is open (RXR-02).
12. **Not covered in any bench:** supply and substrate coupling, IIP2, IIP3, LO leakage to the antenna port, corners
    for linearity (RFR-05, RFR-07).
13. **Analog nets crossing islands without isolation** (`DAC*`, `ADC*`, `BB*_OBS/INJ`): rule or clamp to be
    agreed (`integration/chips/decisions.md` D-ANA).
