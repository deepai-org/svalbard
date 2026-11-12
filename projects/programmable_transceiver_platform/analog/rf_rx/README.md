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

**lna (`pt_lna`)** — single transconductance stage with split I/Q cascodes (RC-16b/e fork A/F/J; input stage
and attenuator redesigned by fork P, RC-16g, 2026-11-11, `scratch/rf-lna-p`). Pseudo-differential CS input
pair (900/0.28 per side, no tail, gate bias from a 22.5 µm replica through 60 kΩ: same 11.7 mA as the old
400/9 pair at a lower density), each drain feeding two cascodes (150/0.28) with 3.6 µm × 1 µm ppoly loads,
one per mixer (`rf_out_*` → rxmix_i, `rf_outq_*` → rxmix_q). ~4.4 pF MIM input coupling (47 µm, pad on the
bottom plate), ~1 pF output coupling. **Input Q** (|X/R| at the pads) is 27–45 extracted (was ~120): the wide
device and the removal of fixed pad-side C let the B18/B25 board ladder with two build-time trimmers (`lna_match.BOARD_TRIM`) hold
S11 ≤ −10 dB over 2.40–2.4835 GHz at every envelope corner; Bode–Fano requires Q ≤ 70 for any network
(`scratch/reviews/physical-limits.md` RX-MATCH). Bond/board tolerance is trimmed per board (cannot be
absorbed on chip). **Pre-LNA attenuator** (RXR max input): six weighted NMOS switches directly
across the two stage-1 gates (3.4 µm × 1/3/7/16/40/120; bits `att0..att4`, `gain_lo` = MSB), ≥ 30 dB with ≤ 6 dB level
gaps (see the evidence level table); the input match is not held while attenuating.
**ct0..ct3** 4-bit shunt-C trim (LSB 25 µm² MIM per leg, differential NMOS switch per bit 30…240 µm),
reset 7; held within 4…10 by the per-board network. `se` = RF_RX_N to VSS through an 11.6 µm MIM + 60 µm
NMOS; a 5.5 µm MIM on RF_RX_P balances the legs. `rt` = Q-spoil, 2 × ~1.5 kΩ across the gates (RC-16h; off unless the B25 tuning needs it). Bypass: `byp` closes
20 µm NMOS from each gate to both mixer feeds. Layout: `lna_layout.py` (compact flat, MIMs over the
devices), 23,980 µm² (budget 24.6k). Benches: view `extpr` = extracted + pad_rf_pair delta + Rg 150 Ω/10 µm;
`extpp` = pessimistic (Rg 200 Ω/10 µm, pad C +30 %); `tb.lna_band` (S11/NF/gain over the band),
`lna_match.att_sweep`, `tb.lna_compression`; deterministic chain NF `tb.chain_det` (DSB/SSB) with the LNA
noise at 3·fLO / 5·fLO measured.

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

**bbfilter_i / bbfilter_q** — fully differential fifth-order Butterworth (fork S redesign,
`bbf_fd.py`, layout `bbf_layout.py`): stage 1 = PGA real pole (FD inverting amplifier, gain k/4,
6-bit conductance bank, pole 1/(R C) independent of gain), stage 2 = Tow-Thomas Q 0.618 (+12 dB step
`gainc0`), stage 3 = Tow-Thomas Q 1.618 (+12 dB `gainc1`). Each integrator is a FD two-stage Miller OTA
with continuous CMFB to `atb_vcm` (2 x 200 kΩ midpoint of the core inputs): the output CM follows the
input CM with gain 1 at every PGA code (RC-17: the old pseudo-differential version multiplied a reference
error by the PGA gain and latched at 42 dB). The Tow-Thomas inverter is a p/n cross-connection, so 5 FD
OTAs replace 14 single-ended ones (5.2 mA vs 6.66 mA). Stage 1: unit R ~40 kΩ, per side C0 (7 µm) +
coarse `bw0..3` (1, 2, 4, 8 x ~200 fF) + fine `fc_fine0..2` (~25/50/100 fF). Biquads (fork U, review fix):
unit R ~20 kΩ and every capacitor x2 (C0 9.9 µm, coarse 1..8 x ~400 fF, fine ~50/100/200 fF), same cutoff
per code: cap code m = 8·bw + fine (0..127), NMOS switches on the virtual-ground side. Q-trim `qt[3:0]`:
the damping resistor is a series string whose binary segments are shorted (Q = q_top (1 − 0.032 k), reset
k = 6 = Butterworth); `gainc` shorts a further 5 % (switch `tgl`). Tow-Thomas lead: two series 8.5 µm MIMs
across the A1→A2 resistor. Fine DCOC (`dcf[7:0]`, `dcf_sign`): sign-magnitude current DAC into the
stage-1 summing nodes through 100 kΩ (≈0.4 mV/LSB at the stage-1 output, ±88..±123 mV); the DAC sits
inside the stage-1 macro (fork U: as a separate macro its high-impedance output nets were routed next to
the filter output, a +42 dB feedback path). Every integrator (OTA + both banks + the resistors landing on
its summing nodes) and the switch/decode group are compact macros (MIMs over active), so the virtual
grounds never leave their cell. Cutoff and Q codes are per-part bring-up trims; the evidence lists the
codes found at each of the 12 envelope corners (CNV-01: Wi-Fi 10.5 MHz with a per-PGA-code cap-code
offset; GX-1: 20–30 MHz with a Q code per coarse PGA state). **Stability (fork U, review NO-GO fix):** the
fork-S biquads oscillated at slow MOS + fast poly/MIM, cap code 0 (integrator loop gain beta A ~ 1.6 at
45 MHz: 100 fF integrator C against ~250 fF of summing-node C). Halving the biquad impedance (beta ~0.44)
and a smaller biquad OTA input pair (40/0.35 vs 60/0.5: less Cgs, ~same gm) fix it; proven by kick +
input-CM-step transients at skewed corners (MOS and R/MIM independent, poly ±25 %) and an AC phase-sign
screen of the whole cap x Q x PGA grid. Digital validator: cap code ≤ 1 requires qt ≥ 6 (margin; this supersedes the fork-S `qt ≥ 12` rule in FS-1). **Fork B (review items 1–5, FS-2):** (a) bank switches ×4 (biquad 4/8/16/32 µm, stage-1 2/4/8/16 µm, fine 4 µm): at 1–8 µm the switch Ron in series with each integrator C moved f3 by ~12 % and opened a ~2.5-LSB gap at every coarse/fine boundary (m 7→8: 11.9→10.0 MHz extracted), so no cap code met 10.5 ± 0.5 MHz; (b) unit R ×0.8 (biquad 16 kΩ, stage 1 32 kΩ; DCOC reference ×1.25 keeps mV/LSB) with the always-on C0 area ×1.3 (biquad 11.3 µm, stage 1 8 µm), so the widest code's integrator frequency stays at fork U's kick-proven value (R ×0.8 alone re-created the oscillation: 3.9 V pp at 30 MHz, ssMOS/ffRC 32 °C, cap 0, qt 6, PGA 42) while one fine LSB is a smaller fraction of f3 (ss still ~10 %, typ ~7.5 %, ff ~5 %); (c) the CNV-01 per-PGA calibration entry is {cap code, Q code}: the cap code closest to 10.5 MHz, and a Q-code vernier (qt ±1/±2, ~3 %/step, peaking/droop/alias re-checked) where no cap code is within 0.3 MHz (ss corners); (d) the DC operating point: ngspice's gmin/source homotopies do not converge on this netlist, so the op row seeds by any method, re-solves by plain Newton from a .nodeset of the seed (no homotopy, ≤ 1 mV on every signal node) and searches for latch states by transients from four extreme initial states (CM 0.3/3.0 V, ±1 V DM) that must all settle to the same equilibrium; (e) bench self-tests (`bbf_bench.validate`): ideal Butterworth, 4kTR noise, fallback detector, and a bistable stand-in that the op/latch bench must fail. AGC: see the RF-RX-NF row (lowest PGA code with ≤ 0.3 dB filter penalty at tt AND ss, chain NF/gain read at run time from `generated/rf_rx_chain.json`).

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
sink, PMOS supply switch, NMOS-only series switch (nfet_06v0 100/0.7) to the pad; inject
via NMOS-only switch (nfet_06v0 60/0.7) pad → `inj_x`. Only NMOS drains touch the pads;
`inj_en` wins over `obs_en`. Pad CM in observe ≈ 0.8 V.
PD29 (HBM core-gate screen): the 3.3 V pad switches saw 6.1–6.5 V gate stress (pad peaks 6.45 V tt /
6.91 V ss/0 °C). 6 V devices alone still fail (6.49 V vs the 6.0 V screen limit, ss/0 °C), because the
unpowered gate driver clamps the gate near 0 V. Each pad-switch gate therefore sits behind 100 kΩ of
ppolyf_u_1k (2×50 µm), with a ~128 fF MIM from the gate to its pad (`TAP_RG`, `TAP_CC` in netlists.py), so the gate
tracks the pad during the pulse. The switches are static (mode bits), so the ~10 MHz gate pole costs nothing. Extracted screen: 0 exceedances in
bb_tap and wmon_bb_tap at tt/27 P_pos, ss/0 P_pos and ss/0 P_neg, with and without the junction model;
worst is 4.88 V (inject gate) against 6.0 V. (risk: PAD-02)

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
| bbfilter `bw[3:0]`, `fc_fine[2:0]` | cap code m = {bw, fc_fine} (7 bits, larger = lower cutoff), reset 8: `rxfilter_x.coefficients.cutoff_code[6:0]` (FS-1) |
| bbfilter `qt[3:0]` | Q-trim, reset 6; a 3-entry table per coarse PGA state (gainc1:gainc0) in wide mode (FS-1) |
| bbfilter `dcf[7:0]`, `dcf_sign` | `bbfilter.offset_{i,q}` 9-bit sign-magnitude, reset 0 (DCOC-F) |
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
| lna | 23980 | 220000 | 0 | 0 | unique match | pass | pass | pass | pass |
| rxmix_i | 76238 | 100000 | 0 | 0 | unique match | pass | pass | pass | pass |
| rxmix_q | 76238 | 100000 | 0 | 0 | unique match | pass | pass | pass | pass |
| bbfilter_i | 341901 | 430000 | 0 | 0 | unique match | pass | pass | pass | pass |
| bbfilter_q | 341901 | 430000 | 0 | 0 | unique match | pass | pass | pass | pass |
| bb_tap | 19511 | none | 0 | 0 | unique match | pass | pass | pass | pass |

### Extracted performance vs target (tt, 27 C, 3.3 V unless a corner table is given)

**lna**

| Metric | Target | Extracted | Pass |
| --- | --- | --- | --- |
| voltage gain into 50 ohm/leg mixer-input model, 2.4 GHz, no board match (dB) | information | -11.2 | info |
| NF, 100 ohm diff source, no board match (dB) | 6.0 | 12.4 | info |
| NF with ideal lossless board L-match (dB) | 6.0 | 2.68 | True |
| differential input impedance at 2.4 GHz (ohm) | 100 (board matching allowed) | 1.19, -49.7 | info |
| pre-LNA attenuator att[4:0] + gain_lo (6 bits, code bit 5 = gain_lo; weights 1/3/7/16/40/120 x 3.4 um): attenuation levels at 2.442 GHz (dB), nominal and both uncertainty ends | >= 30 dB range, level gaps <= 6 dB (RF-RX-AGC, RXR-01) | see generated/lna-evidence.json | False |
| LNA gain compression at the maximum input (RF-RX-MAXIN), tt 27 C 3.3 V, board ladder; (p_dBm, code) -> compression dB | <= 1 dB at -10 dBm (BLE) with the attenuator; <= 1 dB at -20 dBm (Wi-Fi/15.4) | n/a, n/a, n/a, n/a | True |
| supply current active (mA) | <= 11.7 (power budget LNA allocation) | 11.5 | True |
| package-tolerance network at reset (ct=7, se=0, rt=0) vs other codes: matched NF / gain (dB), Zin (ohm), match Q | trim/SE/RT network costs <= 0.5 dB NF (item 2); rt is opt-in |  | info |
| stability: LNA two-port with 1.5 nH RF bonds and 1 nH VDD/VSS bonds (no off-chip decap credited); Edwards-Sinsky mu and Rollett K from Z-parameters, 0.1-12 GHz; and min Re(Zin) at the pads with the REAL extracted rxmix_i/q attached (LO static, both polarities). States: ct 0 / 15, rt on, full attenuation (63), bypass | mu > 1 at every frequency (unconditional), or, if not, Re(Zin) > 0 with the real source/load terminations | see generated/lna-evidence.json | True |
| bench self-tests (bench_selftest.py): hand-calculable and deliberately broken cases of the LNA NF, S11-ladder and harmonic-noise benches | every ok case passes; every broken case fails its check | see generated/lna-evidence.json | True |
| IIP3 (dBm) | 0.0 | n/a | info |
| chain NF, deterministic multitone (tb.chain_det), extpr view, per-board ladder: DSB (zero-IF) / SSB (I channel) (dB); LNA noise at 3 fLO / 5 fLO measured (lna_harmonic), not assumed | on-chip <= 4.1 DSB (RF-RX-NFSYS 8 dB system - 3.91 dB board budget) | 14.1, 17.1 | False |
| RF pad -> I/Q baseband conversion gain with LNA, no board match (dB) |  | gain_i_db=22.3, gain_q_db=22.8 | info |
| same with ideal lossless board L-match (dB) |  | gain_i_db=23, gain_q_db=-54.4 | info |

in-band match with the BOARD TRIMMER network (lna_match.BOARD_TRIM, B18/B25; lossy parts at pessimistic Q, trimmer ESL/terminal C), trimmers + ct (4..10) + rt set once per board, held over the four T/V points; ngspice lna_band on a 0.5 MHz grid: S11 worst over 2.395-2.4885 GHz (band + 5 MHz guard), NF/gain over 2.400-2.4835 GHz. View extpr = extracted + pad_rf_pair + Rg 150 ohm/10 um. Cases: nominal parts/bond and the worst tolerance draw: min / max over 24 rows (corners x cases). Pass: False

| Quantity | min | max |
| --- | --- | --- |
| ct | 4 | 7 |
| rt | 0 | 0 |
| trimmers_pf | 0.982 | 2.35 |
| idd_a | 0.00984 | 0.0134 |
| s11_worst_db | -12.1 | -11.6 |
| s11_worst_db_band_only | -12.8 | -12.4 |
| nf_db | 9.82 | 18.8 |
| gain_db | -17.7 | -7.55 |

same at the HIGH end of the uncertain values (NF / gain worst): Rg 200 ohm/10 um, +25 % device C (low fT), RF pad C +30 %; NF limit applied to the derated NF (simulated + 1.5 dB model derate, spec/design-assumptions.md): min / max over 24 rows (corners x cases). Pass: False

| Quantity | min | max |
| --- | --- | --- |
| ct | 4 | 6 |
| rt | 0 | 0 |
| trimmers_pf | 1.05 | 2.31 |
| idd_a | 0.00984 | 0.0134 |
| s11_worst_db | -11.9 | -11.6 |
| s11_worst_db_band_only | -12.7 | -12.4 |
| nf_db | 13.4 | 22 |
| gain_db | -21.1 | -12 |
| nf_db_derated | 14.9 | 23.5 |

same at the LOW end of the uncertain values (match / detuning / stability worst): Rg 60 ohm/10 um, no extra device C, RF pad C -20 %: min / max over 24 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| ct | 4 | 5 |
| rt | 0 | 0 |
| trimmers_pf | 0.951 | 2.37 |
| idd_a | 0.00984 | 0.0134 |
| s11_worst_db | -12.3 | -11.7 |
| s11_worst_db_band_only | -13 | -12.4 |
| nf_db | 9.15 | 18.3 |
| gain_db | -17.2 | -6.66 |

corner sweep (ext, active): min / max over 12 rows (corners x cases). Pass: info

| Quantity | min | max |
| --- | --- | --- |
| gain_db | -12.9 | -9.73 |
| nf_db | 11.1 | 14 |
| idd_a | 0.00984 | 0.0134 |
| zin_re_ohm | 0.988 | 1.46 |
| zin_im_ohm | -52.5 | -47.2 |

**rxmix_i**

| Metric | Target | Extracted | Pass |
| --- | --- | --- | --- |
| conversion gain, 300 ohm/leg source, 2.4 GHz LO, 5 MHz IF (dB) | 0 (arch, voltage) | 19.3 |  |
| supply current (mA) | 1.0 | 1.9 |  |
| baseband output CM (V) | 1.65 | 1.61 |  |
| TIA output offset raw / after FPGA calibration with the offset DAC (V); DAC LSB (V) | |residual| < 10 mV referred to the filter input | -0.0542, -0.00337, -0.0086 |  |
| chain with LNA (see lna evidence) |  | gain_i_db=17.9, gain_q_db=17 |  |

offset calibration across the envelope (ext; calibrated at each point): min / max over 12 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| raw_offset_v | -0.0586 | -0.0449 |
| lsb_v | -0.0102 | -0.00691 |
| code | -7 | -5 |
| residual_v | -0.00454 | 0.00262 |

corner sweep (ext transient): min / max over 12 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| conversion_gain_db | 17.7 | 20.5 |
| idd_a | 0.00179 | 0.00195 |
| bb_offset_v | -0.0689 | -0.0467 |

**rxmix_q**

| Metric | Target | Extracted | Pass |
| --- | --- | --- | --- |
| conversion gain, 300 ohm/leg source, 2.4 GHz LO, 5 MHz IF (dB) | 0 (arch, voltage) | 19.3 |  |
| supply current (mA) | 1.0 | 1.9 |  |
| baseband output CM (V) | 1.65 | 1.61 |  |
| TIA output offset raw / after FPGA calibration with the offset DAC (V); DAC LSB (V) | |residual| < 10 mV referred to the filter input | -0.0542, -0.00337, -0.0086 |  |
| chain with LNA (see lna evidence) |  | gain_i_db=17.9, gain_q_db=17 |  |

offset calibration across the envelope (ext; calibrated at each point): min / max over 12 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| raw_offset_v | -0.0586 | -0.0449 |
| lsb_v | -0.0102 | -0.00691 |
| code | -7 | -5 |
| residual_v | -0.00454 | 0.00262 |

corner sweep (ext transient): min / max over 12 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| conversion_gain_db | 17.7 | 20.5 |
| idd_a | 0.00179 | 0.00195 |
| bb_offset_v | -0.0689 | -0.0467 |

**bbfilter_i**

| Metric | Target | Extracted | Pass |
| --- | --- | --- | --- |
| RX -3 dB cutoff at the reset cap code 8 (bw0) and reset Q code 6 (Hz) | ~10.5e6 class (trimmed per part: CNV-01 row) | 1.37e+07 |  |
| RX -3 dB cutoff, narrowest (bw=15) (Hz) | 1e5 min | 1.56e+06 |  |
| passband peaking at the reset codes (dB above DC) | <= 1 dB ripple | 0.632 |  |
| PGA gain range (dB, code -6 .. 42) | -6 .. 42 in 3 dB steps | -6.15, 41.6 |  |
| PGA code sweep, reset cap/Q codes (code dB: dc gain dB, peaking dB, f3db Hz) | 3 dB steps (+-0.5 dB), <= 1 dB ripple, cutoff independent of gain |  |  |
| TX direction (tx_in -> out_tx) cutoff and gain |  | dc_gain_db=-0.2, f3db_hz=1.37e+07, peak_gain_db=0.433 |  |
| gain at 20 MHz, widest cap code 0, reset Q code 6, PGA 0 dB (dB relative to DC) (40 MHz channels need ~20 MHz corner) | >= -3 dB (GX-1 trim row: 20..30 MHz per corner) | 1.75 | True |
| supply current, RX active (mA) | allocation 3.77 mA (analog-architecture.json); previous design 6.66 mA | 5.22 |  |
| output CM minus input CM with input CM at 1.75 V (V), PGA 0 / 42 dB (FD OTAs with CMFB to the input CM) | |x| <= 50 mV at every PGA code (no PGA-gain multiplication) | -0.000339, -0.00034 |  |
| passband peaking at max PGA gain, reset codes (dB above DC) | <= 1 dB ripple | 0.0907 |  |
| TX observe through bb_tap into 10 pF: -3 dB (Hz) / gain (dB) / HD3 at 0.4 and 0.8 Vpk diff (dBc) |  | 1.36e+07, -1.57, -69.4, -41.7 |  |
| TX->RX direction switch settling to 1 % (s) | 1e-06 | 1.51e-07 |  |
| bbf_bench self-test: ideal Butterworth AC, resistor-network noise (4kTR), op fallback detector, op/latch detector (bistable stand-in must FAIL), oscillation detector (RHP biquad must FAIL) | every check reproduces its analytic answer and every broken case fails | n/a | True |

Q-trim code sweep (qt 0..15, 6 shown), PGA 0 / 42 dB, widest cap code 0: peaking dB, f3db Hz: min / max over 36 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| pga_db | 0 | 42 |
| qt | 0 | 15 |
| peaking_db | 0 | 8.45 |
| f3db_hz | 1.49e+07 | 5.54e+07 |
| failed corner runs | 36 | |

Wi-Fi 20 MHz at 40 MS/s: per-corner trim (cap code m: bw = m>>3, fc_fine = m&7; Q code) and a per-PGA-code cap-code offset table (FS-1), checked at EVERY PGA code -6..42 dB: f3 = 10.5 +- 0.5 MHz, droop <= 3 dB at 8.75 MHz, >= 38 dB at 31.25 MHz (alternate-channel alias), peaking <= 1 dB: min / max over 12 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| cap_code_pga0 | 8 | 20 |
| qt | 6 | 6 |

wide range: per-corner cap code (0..7) and a Q code per coarse PGA state (0 / 21 / 42 dB shown) with f3 in 20..30 MHz, peaking <= 1 dB, droop <= 3 dB at 19.1 MHz: min / max over 12 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| cap_code | 0 | 3 |

PGA 42 dB, widest cap code 0, Q code 15: f3db Hz, peaking dB: min / max over 12 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| idd_a | 0.00499 | 0.00532 |
| out_cm_minus_in_v | -0.000396 | -0.000222 |
| dc_gain_db | 41.4 | 41.6 |
| f3db_hz | 1.37e+07 | 3.14e+07 |
| peaking_db | 0 | 0 |
| rel_pass_db | -1.31 | -0.251 |
| rel_alias_db | -19.8 | -2.97 |
| rel_wide_db | -5.92 | -1.32 |

PGA 42 dB, input CM 1.75 V: DC operating point. ngspice gmin/source homotopies do NOT converge on this netlist (seed = pseudo-transient); proof of a DC solution = plain Newton re-solve from a .nodeset of the seed (no homotopy, no fallback, <= 10 mV from the seed on the signal nodes); latch search = transients (uic) from 4 extreme initial states (CM 0.3 / 3.0 V, +-1 V DM on every stage output and OTA first-stage node) that must settle to the same state: min / max over 5 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| out_cm_minus_in_v | -0.00034 | -4.91e-05 |
| out_diff_v | -2e-05 | -9.39e-06 |

PGA 42 dB, reset cap/Q codes (8 / 6), input CM 1.75 V: supply + controls ramp 0 -> final in 2 us; output at 18..20 us: min / max over 5 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| out_cm_minus_in_v | -0.00034 | -4.91e-05 |
| out_diff_v | -2e-05 | -9.35e-06 |
| out_diff_pp_v | 2.98e-09 | 4.95e-08 |

stability, every validator-allowed combination: kick (20 mV, 10 ns) + held +100 mV input-CM step transient at SKEWED corners (MOS and poly-R/MIM corners independent, poly sheet +-25 %: design-assumptions.md); every stage DM and CM (s1, bp1, lp1, bp2, co) residual at 5-6 us. Worst cases by construction: lowest cap code (highest integrator frequency, lowest OTA feedback factor) at the highest allowed Q (validator: cap code <= 1 requires qt >= 6; qt 0 also run), every coarse PGA state (0/21/42 dB); cap codes 2/4/16 at qt 0 and 15; cap code 127 at PGA -6 dB (highest feedback factor): min / max over 40 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| pga_db | -6 | 42 |
| cap_code | 0 | 127 |
| qt | 0 | 15 |
| worst_residual_pp_v | 2.97e-08 | 6.8e-05 |
| worst_f_hz | 1e+06 | 2e+06 |

fine DC-offset DAC (sign + 8 bits into the stage-1 summing nodes): stage-1 output step, range, monotonicity: min / max over 3 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| lsb_mv | 0.334 | 0.471 |
| full_scale_mv | -120 | 120 |
| dnl_lsb_min | -0.118 | -0.1 |
| dnl_lsb_max | 0.323 | 0.335 |

filter noise (PGA code, reset cap/Q codes): input-referred density at 1 / 5 MHz, output rms 0.1-10 MHz, and the chain NF with the filter (F_chain + (v_in,filter / v_src at the filter input)^2; LNA + mixer gain 35.34 dB, DSB source noise at the filter input 106 nV/rtHz, chain NF without the filter 4.22 dB DSB tt / 5.936 ss (read at run time from generated/rf_rx_chain.json); AGC row = lowest PGA code meeting <= 0.3 dB at BOTH tt and ss): min / max over 14 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| pga_db | 0 | 42 |
| cap_code | 8 | 8 |
| qt | 6 | 6 |
| out_rms_v | 0.00034 | 0.00649 |
| in_rms_v | 5.14e-05 | 0.000406 |
| in_nv_rthz_1mhz | 17.1 | 110 |
| in_nv_rthz_5mhz | 15.8 | 118 |
| chain_src_nv_rthz | 68.4 | 106 |
| delta_f_at_5mhz | 0.022 | 2.98 |
| chain_nf_dsb_db_no_filter | 4.22 | 5.94 |
| chain_nf_dsb_db_with_filter | 4.26 | 8.39 |

corner sweep (ext, RX reset cap code 8 (bw0), gain 0, reset Q code): min / max over 12 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| f3db_hz | 1.03e+07 | 1.95e+07 |
| dc_gain_db | -0.293 | -0.225 |
| peak_gain_db | 0.207 | 0.778 |
| idd_a | 0.00499 | 0.00532 |
| out_cm_v | 1.65 | 1.65 |

**bbfilter_q**

| Metric | Target | Extracted | Pass |
| --- | --- | --- | --- |
| RX -3 dB cutoff at the reset cap code 8 (bw0) and reset Q code 6 (Hz) | ~10.5e6 class (trimmed per part: CNV-01 row) | 1.37e+07 |  |
| RX -3 dB cutoff, narrowest (bw=15) (Hz) | 1e5 min | 1.56e+06 |  |
| passband peaking at the reset codes (dB above DC) | <= 1 dB ripple | 0.632 |  |
| PGA gain range (dB, code -6 .. 42) | -6 .. 42 in 3 dB steps | -6.15, 41.6 |  |
| PGA code sweep, reset cap/Q codes (code dB: dc gain dB, peaking dB, f3db Hz) | 3 dB steps (+-0.5 dB), <= 1 dB ripple, cutoff independent of gain |  |  |
| TX direction (tx_in -> out_tx) cutoff and gain |  | dc_gain_db=-0.2, f3db_hz=1.37e+07, peak_gain_db=0.433 |  |
| gain at 20 MHz, widest cap code 0, reset Q code 6, PGA 0 dB (dB relative to DC) (40 MHz channels need ~20 MHz corner) | >= -3 dB (GX-1 trim row: 20..30 MHz per corner) | 1.75 | True |
| supply current, RX active (mA) | allocation 3.77 mA (analog-architecture.json); previous design 6.66 mA | 5.22 |  |
| output CM minus input CM with input CM at 1.75 V (V), PGA 0 / 42 dB (FD OTAs with CMFB to the input CM) | |x| <= 50 mV at every PGA code (no PGA-gain multiplication) | -0.000339, -0.00034 |  |
| passband peaking at max PGA gain, reset codes (dB above DC) | <= 1 dB ripple | 0.0907 |  |
| TX observe through bb_tap into 10 pF: -3 dB (Hz) / gain (dB) / HD3 at 0.4 and 0.8 Vpk diff (dBc) |  | 1.36e+07, -1.57, -69.4, -41.7 |  |
| TX->RX direction switch settling to 1 % (s) | 1e-06 | 1.51e-07 |  |
| bbf_bench self-test: ideal Butterworth AC, resistor-network noise (4kTR), op fallback detector, op/latch detector (bistable stand-in must FAIL), oscillation detector (RHP biquad must FAIL) | every check reproduces its analytic answer and every broken case fails | n/a | True |

Q-trim code sweep (qt 0..15, 6 shown), PGA 0 / 42 dB, widest cap code 0: peaking dB, f3db Hz: min / max over 36 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| pga_db | 0 | 42 |
| qt | 0 | 15 |
| peaking_db | 0 | 8.45 |
| f3db_hz | 1.49e+07 | 5.54e+07 |
| failed corner runs | 36 | |

Wi-Fi 20 MHz at 40 MS/s: per-corner trim (cap code m: bw = m>>3, fc_fine = m&7; Q code) and a per-PGA-code cap-code offset table (FS-1), checked at EVERY PGA code -6..42 dB: f3 = 10.5 +- 0.5 MHz, droop <= 3 dB at 8.75 MHz, >= 38 dB at 31.25 MHz (alternate-channel alias), peaking <= 1 dB: min / max over 12 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| cap_code_pga0 | 8 | 20 |
| qt | 6 | 6 |

wide range: per-corner cap code (0..7) and a Q code per coarse PGA state (0 / 21 / 42 dB shown) with f3 in 20..30 MHz, peaking <= 1 dB, droop <= 3 dB at 19.1 MHz: min / max over 12 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| cap_code | 0 | 3 |

PGA 42 dB, widest cap code 0, Q code 15: f3db Hz, peaking dB: min / max over 12 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| idd_a | 0.00499 | 0.00532 |
| out_cm_minus_in_v | -0.000396 | -0.000222 |
| dc_gain_db | 41.4 | 41.6 |
| f3db_hz | 1.37e+07 | 3.14e+07 |
| peaking_db | 0 | 0 |
| rel_pass_db | -1.31 | -0.251 |
| rel_alias_db | -19.8 | -2.97 |
| rel_wide_db | -5.92 | -1.32 |

PGA 42 dB, input CM 1.75 V: DC operating point. ngspice gmin/source homotopies do NOT converge on this netlist (seed = pseudo-transient); proof of a DC solution = plain Newton re-solve from a .nodeset of the seed (no homotopy, no fallback, <= 10 mV from the seed on the signal nodes); latch search = transients (uic) from 4 extreme initial states (CM 0.3 / 3.0 V, +-1 V DM on every stage output and OTA first-stage node) that must settle to the same state: min / max over 5 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| out_cm_minus_in_v | -0.00034 | -4.91e-05 |
| out_diff_v | -2e-05 | -9.39e-06 |

PGA 42 dB, reset cap/Q codes (8 / 6), input CM 1.75 V: supply + controls ramp 0 -> final in 2 us; output at 18..20 us: min / max over 5 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| out_cm_minus_in_v | -0.00034 | -4.91e-05 |
| out_diff_v | -2e-05 | -9.35e-06 |
| out_diff_pp_v | 2.98e-09 | 4.95e-08 |

stability, every validator-allowed combination: kick (20 mV, 10 ns) + held +100 mV input-CM step transient at SKEWED corners (MOS and poly-R/MIM corners independent, poly sheet +-25 %: design-assumptions.md); every stage DM and CM (s1, bp1, lp1, bp2, co) residual at 5-6 us. Worst cases by construction: lowest cap code (highest integrator frequency, lowest OTA feedback factor) at the highest allowed Q (validator: cap code <= 1 requires qt >= 6; qt 0 also run), every coarse PGA state (0/21/42 dB); cap codes 2/4/16 at qt 0 and 15; cap code 127 at PGA -6 dB (highest feedback factor): min / max over 40 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| pga_db | -6 | 42 |
| cap_code | 0 | 127 |
| qt | 0 | 15 |
| worst_residual_pp_v | 2.97e-08 | 6.8e-05 |
| worst_f_hz | 1e+06 | 2e+06 |

fine DC-offset DAC (sign + 8 bits into the stage-1 summing nodes): stage-1 output step, range, monotonicity: min / max over 3 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| lsb_mv | 0.334 | 0.471 |
| full_scale_mv | -120 | 120 |
| dnl_lsb_min | -0.118 | -0.1 |
| dnl_lsb_max | 0.323 | 0.335 |

filter noise (PGA code, reset cap/Q codes): input-referred density at 1 / 5 MHz, output rms 0.1-10 MHz, and the chain NF with the filter (F_chain + (v_in,filter / v_src at the filter input)^2; LNA + mixer gain 35.34 dB, DSB source noise at the filter input 106 nV/rtHz, chain NF without the filter 4.22 dB DSB tt / 5.936 ss (read at run time from generated/rf_rx_chain.json); AGC row = lowest PGA code meeting <= 0.3 dB at BOTH tt and ss): min / max over 14 rows (corners x cases). Pass: True

| Quantity | min | max |
| --- | --- | --- |
| pga_db | 0 | 42 |
| cap_code | 8 | 8 |
| qt | 6 | 6 |
| out_rms_v | 0.00034 | 0.00649 |
| in_rms_v | 5.14e-05 | 0.000406 |
| in_nv_rthz_1mhz | 17.1 | 110 |
| in_nv_rthz_5mhz | 15.8 | 118 |
| chain_src_nv_rthz | 68.4 | 106 |
| delta_f_at_5mhz | 0.022 | 2.98 |
| chain_nf_dsb_db_no_filter | 4.22 | 5.94 |
| chain_nf_dsb_db_with_filter | 4.26 | 8.39 |

corner sweep (ext, RX reset cap code 8 (bw0), gain 0, reset Q code): min / max over 12 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| f3db_hz | 1.03e+07 | 1.95e+07 |
| dc_gain_db | -0.293 | -0.225 |
| peak_gain_db | 0.207 | 0.778 |
| idd_a | 0.00499 | 0.00532 |
| out_cm_v | 1.65 | 1.65 |

**bb_tap**

| Metric | Target | Extracted | Pass |
| --- | --- | --- | --- |
| observe gain in -> pad, 10 pF || 100 k load (dB) | ~0 (buffer) | -1.37 |  |
| observe -3 dB bandwidth into 10 pF (Hz) | >= 20e6 | 7.13e+07 |  |
| gain at 20 MHz (dB), AC / transient 0.4 Vpp diff |  | -1.72, -1.72 |  |
| pad common mode in observe (V) |  | 0.818 |  |
| inject pad -> chain node gain (dB) |  | -0.0962 |  |
| supply current observing (mA) |  | 1.01 |  |

corner sweep (ext observe): min / max over 12 rows (corners x cases). Pass: 

| Quantity | min | max |
| --- | --- | --- |
| lf_gain_db | -1.49 | -1.29 |
| f3db_hz | 6.4e+07 | 7.74e+07 |
| gain_20mhz_db | -1.9 | -1.58 |
| pad_cm_v | 0.703 | 0.933 |
| idd_a | 0.000996 | 0.00103 |

### RF chain (extracted LNA + both extracted mixers, ideal LO)

| Case | LO (Hz) | I gain (dB) | Q gain (dB) | Supply (mA) |
| --- | --- | --- | --- | --- |
| ext_u | 2.4e+09 | 22.3 | 22.8 | 15.3 |
| ext_m | 2.4e+09 | 23 | -54.4 | 15.4 |
| ext_byp | 2.4e+09 | 5.31 | 3.82 | 3.8 |
| ext_m_1200MHz | 1.2e+09 | 50.2 | 50.2 | 15.3 |
| ext_m_600MHz | 6e+08 | 55.4 | 55 | 15.4 |
| det_lna_matched_extpr: chain NF DSB 14.1 / SSB 17.1 dB (corner ['typical', 27, 3.3]) | 2.4e9 | | | |
| det_lna_matched_extpr_ss_32_3.15: chain NF DSB 16.5 / SSB 19.4 dB (corner ['ss', 32, 3.15]) | 2.4e9 | | | |

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
`run_rf_rx.sh` to refresh the hash). All other records match current sources. (risk: MOD-05)

## 7. Limitations and open items

1. **Mixer DC offset** from LO coupling in the routed connections to the quad:
   raw −45..−59 mV at the TIA output over the envelope (−47..−69 mV with an RF
   tone). Calibrated per envelope point with the offset DAC (codes −5..−7) the
   residual is ≤ 4.5 mV (target 10 mV); one tt code reused everywhere leaves
   more, so the FPGA should recalibrate on temperature/supply change. Filter OTA
   offsets are not corrected. (risk: RXR-02)
2. **Chain NF**: deterministic multitone `tb.chain_det` (DSB/SSB, LO-harmonic folding measured), results in the
   RF chain table above and `generated/rf_rx_chain.json`; target ≤ 4.1 dB DSB on chip. Dominated by the TIA OTA. (risk: RFR-01)
3. **LNA** (RC-16g/h): matched with the B18/B25 board trimmer network (two trimmers set once at build); in-band S11, NF and gain
   per corner and at both model-uncertainty ends in `generated/lna-evidence.json` (each row has a pass field). Open: the derated NF
   at the high (Rg 200, +25 % C) end and the chain NF DSB ≤ 4.1 dB fail (TIA-limited); stability is conditional (mu < 1 below
   ~0.5 GHz) with Re(Zin) > 0 for the real terminations. IIP3 not simulated. (risks: RFR-01, RFR-10, RFR-11)
4. **Filter** (fork S FD redesign): trimmed per part, extracted at all 12 envelope corners: Wi-Fi
   10.5 MHz (droop ≤ 2.2 dB at 8.75 MHz, ≥ 44 dB at 31.25 MHz at PGA 0/21/42 dB) and 20–30 MHz wide
   range (Q code per coarse PGA state); narrowest ~1.2 MHz (LoRa 203/406 kHz still needs a lower
   cutoff); cutoff drops ~10 % from PGA 0 to 42 dB (stage-1 loop at noise gain 9); 5.2 mA per path
   (allocation 3.77 mA). Calibration (inject → observe) not modelled; no Monte Carlo. (risk: RFR-02, CNV-01)
5. **Mixer**: 1.9 mA (target 1.0 mA); output CM 1.61 V, which the filter passes
   through to the ADC/txmix. (risk: PWR-08)
6. **bb_tap**: pad CM ~0.8 V (external ADC must accept it); NMOS-only switches
   limit inject to ≲ 2 V on the pad. (risk: RFR-09)
7. **Layout sensitivity**: each integrator is a compact macro (virtual grounds local); recheck
   extracted bandwidth and the trim rows after any re-layout. (risk: RFR-02)
8. LO modelled as ideal 0/VDD square (LO generator not co-simulated); I/Q
   mismatch, IIP2/IIP3, LO leakage, Monte Carlo, aging and EM of the 0.4 µm M4
   LNA supply tracks not covered. (risk: RFR-05)

Stretch (non-gating): 20 MHz corner only at fast corners (−15.5 dB at 20 MHz,
tt); RX active current 18.2 mA (LNA 2.75 + 2 × 1.90 + 2 × 5.82), +1.0 mA per
observing tap; LO /2 and /4: 36 dB conversion gain at 1.2 GHz and 600 MHz LO vs
26–27 dB at 2.4 GHz (ideal board match, `generated/rf_rx_chain.json`).
