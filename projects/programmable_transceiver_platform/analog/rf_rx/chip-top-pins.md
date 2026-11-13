# RF RX family: exact pins and connection intent for chip-top integration

Written 2026-11-13 by the RF RX owner for the chip-top integration agent (`scratch/chip-top/`), answering
mode-walk rows MW-5 (LNA/rxmix binding), MW-4 (bbfilter controls) and MW-20 (LO drive). Pin order is the
`.subckt` order of the block `.spice` files in this directory (single source: `netlists.py`).

**Status of the cells.** `lna`, `rxmix_i`, `rxmix_q` in the working tree are the RC-16j/k LNTA with ON-CHIP source
degeneration (coordinator decision 2026-11-13) and the fork V TIA. They are NOT published yet (review
`scratch/review-lna3/`, risks RFR-11…14), but the pin lists below are the intended final ones. `bbfilter_i/q` and
`bb_tap` are the published cells.

## 1. pt_lna

```
.subckt pt_lna rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt
+ island_off atb_nbias atb_vdcm VDD VSS ct3 att0 att1 att2 att3 att4 src_p src_n tank_p tank_n lobias
```

| Pin | Connect to | Notes |
| --- | --- | --- |
| `rf_in_p`, `rf_in_n` | protected RF_RX_P / RF_RX_N pad nodes (`pad_rf_pair`) | AC-coupled inside the LNA (MIM); no DC path to the pad |
| `rf_out_p`, `rf_out_n` | `rxmix_i.rf_p`, `rxmix_i.rf_n` ONLY | one LNA output pair per mixer; each pair has its own 16 µm coupling MIM from the tank |
| `rf_outq_p`, `rf_outq_n` | `rxmix_q.rf_p`, `rxmix_q.rf_n` ONLY | must not be left open and must not be shorted to `rf_out_*` (the assembly rule that puts both mixers on `rf_out` is wrong for this cell) |
| `tank_p`, `tank_n` | one `lna_ind` spiral each: spiral terminal A = `VDD` (RAIL_rf), terminal B = `tank_p` (resp. `tank_n`) | two instances of `generated/lna_ind.gds` (`pt_lna_ind`, 170 µm, 3 turns, 1.35 nH, DRC-only cell, no LVS device); they also carry the LNA DC current (≈ 9.7 mA each, RX bias); abut the LNA tank pins, keep the two spirals ≥ 1 diameter apart or orthogonal, no metal fill / MIM / decap over them. Without the spirals the LNA has no DC feed and no gain |
| `src_p`, `src_n` | one `lna_deg` spiral each: terminal A = `src_p` (resp. `src_n`), terminal B = the LNA's VSS (AGND_RX) | NOT pads (the LNA_SRC pad sites are released, RC-16t). `pt_lna_deg`: 140 µm, 2 turns, 0.47 nH, 25.2k µm², DRC-only cell (generator `lna_spiral.G_DEG`); abut the LNA source pins, ground end straight onto the LNA ground strap; no fill / MIM / decap over them; they carry the CS DC current (≈ 9.5 mA each) |
| `ibias` | 10 µA sourced into the pin from the RF bias bank (one branch for the LNA) | NMOS diode on the pin |
| `en` | `lna.state != off` | |
| `gain_lo` | attenuator MSB (code bit 5) | NOT a −6 dB step; see `att` |
| `att0..att4` | `lna.match.att[4:0]` | current-steering attenuator, code = {gain_lo, att4..att0}; level table in `generated/lna-evidence.json` (to be regenerated) |
| `byp` | `debug.rf_rx_bypass.lna` | pad → both mixer feeds through a series MIM; use with `en` = 0 |
| `ct0..ct3` | `lna.match.ctrim[3:0]`, reset 7 | tank tune (not an input-match trim any more) |
| `se`, `rt` | `lna.match.se`, `lna.match.rterm`, reset 0 | |
| `lobias` | NEW register bit `lna.bias.lo` (reset 0); the mode validator forces 1 whenever the TX chain is on (rf_tx and duplex) | 1 = reduced LNA bias |
| `island_off` | RF island switch `ISO` output | |
| `atb_nbias`, `atb_vdcm` | ATB mux (code 16 = lna_bias; `atb_vdcm` needs a code) | |
| `VDD`, `VSS` | RAIL_rf (VDD_RF_SW), AGND_RX (RC-4) | |

## 2. pt_rxmix_i / pt_rxmix_q

```
.subckt pt_rxmix_i rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off
+ atb_vcm atb_vbp VDD VSS
```

There is no `hib` pin (fork V TIA; the fork-P2 switched-tail option that added it is not used).

| Pin | Connect to | Notes |
| --- | --- | --- |
| `rf_p`, `rf_n` | rxmix_i: `lna.rf_out_p/n`; rxmix_q: `lna.rf_outq_p/n` | |
| `lo_p`, `lo_n` | rxmix_i: LO_IP / LO_IN; rxmix_q: LO_QP / LO_QN | gates only. MW-20: the cell was characterised with a 0/VDD square LO; see section 5 |
| `bb_p`, `bb_n` | `bbfilter_x.rx_in_p/n` | high-Z when `en` = 0 |
| `ibias` | 10 µA per mixer from the RF bias bank | |
| `en` | `rxmix_x.state != off` | |
| `ofs0..ofs4`, `ofs_sign` | `pga_x.offset.code` sign-magnitude (README §4) | |
| `island_off` | RF island switch `ISO` output | |
| `atb_vcm`, `atb_vbp` | ATB mux (code 17) | |
| `VDD`, `VSS` | RAIL_rf, AGND_RX | |

`rxmix_q` is placed mirrored (I1 in interface-changes.md): confirmed, nothing in the cell depends on orientation.

## 3. pt_bbfilter_i / pt_bbfilter_q (MW-4: true control pins and intended codes; cell unchanged)

```
.subckt pt_bbfilter_i rx_in_p rx_in_n tx_in_p tx_in_n inj_p inj_n out_rx_p out_rx_n out_tx_p out_tx_n obs_p obs_n
+ ibias en dir_tx inj rx_direct byp_s1 byp_s23 obs_sel0 obs_sel1 bw0 bw1 bw2 bw3 gain0 gain1 gain2 gain3 gain4 gain5
+ gainc0 gainc1 qt0 qt1 island_off atb_vcm atb_vbp VDD VSS qt2 qt3 fc_fine0 fc_fine1 fc_fine2
+ dcf0 dcf1 dcf2 dcf3 dcf4 dcf5 dcf6 dcf7 dcf_sign
```

Every control is a static active-high level; I and Q are separate cells and need separate field sets (the cutoff, Q and
DCOC codes are per-part trims and differ between I and Q).

| Pins | Width | Reset | Meaning |
| --- | --- | --- | --- |
| `en` | 1 | 0 | bias bank + OTAs on. Must be decoded: `consolidation.bbfilter.direction != isolated`. With `en` = 0 the cell is off regardless of every other bit |
| `dir_tx` | 1 | 0 | 0 = RX (rx_in → out_rx), 1 = TX (tx_in → out_tx) |
| `inj`, `rx_direct`, `byp_s1`, `byp_s23` | 1 each | 0 | inject from bb_tap; filter-less RX; stage-1 bypass; stage-2/3 bypass |
| `obs_sel1:0` | 2 | 0 | 00 off, 01 rx_in, 10 after PGA, 11 filter out |
| `gain5:0` (k), `gainc1`, `gainc0` | 6 + 2 | k = 4 (`gain2`), gainc = 0 → 0 dB | stage-1 gain = k/4 (k = conductance code, **k = 0 mutes stage 1**); `gainc0`, `gainc1` add +12 dB each in stages 2 and 3. The register value is a dB index, mapped by the LUT below (17 entries, −6…+42 dB in 3 dB steps). A 4-bit linear field written straight to `gain3:0` reaches only k = 15 → +11.5 dB |
| `bw3:0`, `fc_fine2:0` | 4 + 3 | cap code m = 8·bw + fine = 8 (bw = 1, fine = 0) | larger = lower cutoff; per-part trim, per PGA code offset (CNV-01) |
| `qt3:0` | 4 | 6 | Q trim; validator: cap code m ≤ 1 requires qt ≥ 6 |
| `dcf7:0`, `dcf_sign` | 8 + 1 | 0 | fine DC offset DAC, sign-magnitude, ≈ 0.4 mV/LSB at the stage-1 output |
| `ibias` | – | – | 10 µA per filter |
| `island_off`, `atb_vcm`, `atb_vbp` | – | – | island ISO; ATB code 19 |

PGA LUT (`netlists.GAIN_TABLE`; bits listed are the ones driven high):

| dB | k (`gain5:0`) | gainc0 | gainc1 | | dB | k | gainc0 | gainc1 |
| ---: | ---: | :-: | :-: | --- | ---: | ---: | :-: | :-: |
| −6 | 2 | 0 | 0 | | 21 | 12 | 1 | 0 |
| −3 | 3 | 0 | 0 | | 24 | 17 | 1 | 0 |
| 0 | 4 | 0 | 0 | | 27 | 24 | 1 | 0 |
| 3 | 6 | 0 | 0 | | 30 | 35 | 1 | 0 |
| 6 | 8 | 0 | 0 | | 33 | 12 | 1 | 1 |
| 9 | 12 | 0 | 0 | | 36 | 17 | 1 | 1 |
| 12 | 17 | 0 | 0 | | 39 | 25 | 1 | 1 |
| 15 | 24 | 0 | 0 | | 42 | 36 | 1 | 1 |
| 18 | 35 | 0 | 0 | | | | | |

The LUT can live in the digital macro (register = 5-bit dB index 0…16, reset index 2 = 0 dB) or in the FPGA (register =
raw {gainc1, gainc0, gain5:0}, reset 0x04); the cell does not care. The reset value must never be k = 0.

## 4. pt_bb_tap (unchanged)

```
.subckt pt_bb_tap in_p in_n pad_p pad_n inj_p inj_n ibias obs_en inj_en island_off atb_nbias VDD VSS
```

`in_p/n` = `bbfilter_x.obs_p/n`; `inj_p/n` = `bbfilter_x.inj_p/n`; `pad_p/n` = BB_I / BB_Q pad nodes; `obs_en`, `inj_en`
from `debug.bb_tap.mode` (README §4).

## 5. LO drive (MW-20)

The RX mixers are passive NMOS quads at a 1.65 V common mode. All published RX gain / NF / offset numbers used an ideal
0/VDD square LO. The real LO chain (`pt_lo_ext` and the CML path) delivers a sine about ≈ 2.44 V with a peak on-Vgs of
only 0.9–1.16 V. Bench support: `tb.LO_REAL`, `tb.lo_sources`, `lo=` argument of `tb.rxmix_tran` and `tb.chain_det`
(sine models of the three delivered levels, or `('include', deck)` for the LO owner's extracted distribution). Results
are recorded in `scratch/rf-lna-p/NOTES.md` (v8/mwlo.py, v8/cxlo.py) until the family is republished. Integration must
not assume the square-LO numbers.
