# RF transmit family: `txmix_i`, `txmix_q`, `txsum`, `rfdriver`

Transistor-level 2.4 GHz transmit path:
`bbfilter (TX direction, analog/rf_rx) → txmix_i/q → txsum → rfdriver → RF_TX pad`.
TX reconstruction filtering is in the shared `bbfilter_i/q`; each mixer also has a direct DAC input (filter
bypass), so TX → RX loopback works while the filter serves RX. No inductors on chip: the output stage is DC-fed
and matched by the board. Numbers come from `generated/*-evidence.json`, `generated/rf_tx-sim-ext.json` and
`generated/rf_tx-modulation.json`; nothing here is silicon or Monte Carlo evidence. Risks: IDs refer to
`spec/risk-register.md`.

## Status

All four blocks are published in `generated/` and bound in `integration/top/pt_chip.conn` (rf_tx island).
Every `source_hashes` and `output_hashes` entry in the evidence files matches the current sources, GDS and
extracted netlists.

| Block | Cell | Area µm² (bbox µm) | Ceiling µm² | Magic DRC / KLayout DRC | LVS |
| --- | --- | ---: | ---: | --- | --- |
| `txmix_i`, `txmix_q` | `pt_txmix_i/q` | 21,788 (237.86 × 91.6) | 27,300 | 0 / 0 | unique |
| `txsum` | `pt_txsum` | 4,165 (83.94 × 49.62) | 5,600 | 0 / 0 | unique |
| `rfdriver` | `pt_rfdriver` | 97,609 (479.98 × 203.36) | 98,100 | 0 / 0, antenna 0 | unique, name-equivalent |

| Test | txmix_i/q | txsum | rfdriver |
| --- | --- | --- | --- |
| safe | pass | pass | pass |
| clean | pass | pass | pass |
| observable | open | open | open |
| fallback | open | open | pass |
| stable | – | – | pass |

## Files and how to run

| File | Content |
| --- | --- |
| `circuits.py` | single source of all netlists; writes `<block>.spice` (top cell `pt_<block>`) |
| `layoutlib.py` | row/channel Magic generator (PCells, M2–M5 routing), DRC, extraction, Netgen LVS |
| `generate.py`, `generate_<block>.py` | per-block placement/routing options; publish to `generated/` |
| `gds_export.py` | GDS re-export with Magic 8.3.678 (HRES/RES_MK marker count) and KLayout GF180 DRC |
| `simulate.py`, `run_benches.py` | ngspice benches: block, chain, matched, corners, safety, stability, stretch |
| `tx_modulation.py` | HE20 OFDM EVM / ACLR / mask from the extracted AM-AM / AM-PM (memoryless model) |
| `evidence.py` | writes `generated/<block>-evidence.json` |
| `generated/` | `<block>.gds/.mag/.ext.spice`, `-drc.txt`, `-lvs.txt`, `-layout.json`, `-gds-export.json`, `-klayout-drc.lyrdb`, `-evidence.json`, `rf_tx-sim-{ext,sch}.json`, `rf_tx-modulation.json` |

`./run_rf_tx.sh` regenerates everything. Images, all `--network none`: Magic DRC, extraction and Netgen LVS in
`svalbard/librelane-gf180-canary:2026.08` (Magic 8.3.623, Netgen 1.5.316); GDS export (Magic 8.3.678, which
writes the HRES 62/0 marker), KLayout DRC and ngspice in `hpretl/iic-osic-tools@sha256:89641950…`. Raw work:
`scratch/rf_tx/`.

## Circuits

| Block | Topology |
| --- | --- |
| `txmix_i/q` | Double-balanced Gilbert upmixer: NMOS transconductor with `ppolyf_u_1k` degeneration, two ~0.5 mA tails from the 10 µA diode, four NMOS commutators, open-drain current outputs. NMOS input switches select `bb_*` (`sel_dac=0`) or `dac_*` (`sel_dac=1`). `sat=1` shorts the degeneration (constant-envelope mode). |
| `txsum` | I and Q mixer drains joined at `out_*`; `ppolyf_u` load per leg to a PMOS header (open when `en=0`); outputs clamp to VSS when off. No current of its own: it carries the two mixer tails (2.0 mA). |
| `rfdriver` | Three pre-amplifiers; NMOS source followers in an isolated p-well; output pair (640/0.28 per side) with binary tail slices selected by `g3..g0`; `nfet_06v0` cascodes (960/0.7 per leg) with their drains on the pads, so the 3.3 V pair is shielded from the pad swing; PMOS header. The pads are DC-fed from the board (balun centre tap or chokes to the rf_tx island rail). `bypass=1`: T switch (`pfet_06v0` in its own n-well, shunt to VSS when open) connects `in_*` to `pad_*` with the amplifier off. `se=1`: `pad_n` cascode off, that leg steered into an on-chip dummy load. `mute=1`: output tails off. |

## Interfaces

Pin lists (`<block>.spice`):

```
.subckt pt_txmix_i  VDD VSS bb_p bb_n dac_p dac_n lo_p lo_n out_p out_n ibias en sel_dac sat atb_bias atb_tail
.subckt pt_txsum    VDD VSS i_p i_n q_p q_n out_p out_n en atb_cm
.subckt pt_rfdriver VDD VSS in_p in_n pad_p pad_n ibias en mute bypass g0 g1 g2 g3 se atb_bias atb_pre atb_cm
```

- **Supplies**: `VDD` = rf_tx island rail (3.3 V), `VSS`.
- **LO** (`lo_p/n`, nets `LO_IP/IN`, `LO_QP/QN`): benches assume a differential rail-to-rail square at 2.44 GHz,
  50 % duty, DC-coupled to the commutator gates, Q delayed by T/4.
- **Baseband** (`bb_*` from `bbfilter_x.out_tx`, `dac_*` from the DAC): voltage mode, 1.65 V common mode,
  DC-coupled, no DC load; 135 fF when selected, 33 fF when off. The benches drive 0.3 V (linear mode) and 1.0 V
  (saturated mode) DC or peak per channel.
- **Bias**: `ibias` 10 µA into an NMOS diode per block (txsum has none).
- **RF_TX pad and board**: the load must be DC-blocked and must supply the DC feed from the rf_tx island rail
  (BRD-01). The pads rest at the rail (3.28 V enabled). Bench network: per-leg chokes of 2.23 nH (Q 30) that
  resonate the pad susceptance (pad admittance 1.22 + j14.6 mS differential at tt, code 15), DC blocks, an ideal
  200:50 Ω balun and a 1.0 dB pad for balun loss, 50 Ω load. "Matched" below means this network; all matched
  powers are after the balun loss. The pad is modelled as 2 Ω + 1 pF per leg.

### Controls (active high, core domain, safe at any level with the island off)

| Port | Block | Register source | Reset |
| --- | --- | --- | --- |
| `en` | txmix_i/q | `txmix_{i,q}.state` ≠ off | 0 |
| `sel_dac` | txmix_i/q | `consolidation.bbfilter.tx_dac_direct` | 0 |
| `sat` | txmix_i/q | `consolidation.txmix.sat_mode` | 0 |
| `en` | txsum | `txsum.state` ≠ off | 0 |
| `en` | rfdriver | `rfdriver.state` ≠ off | 0 |
| `g3..g0` | rfdriver | `rfdriver.gain.code` | 12 |
| `se` | rfdriver | `rfdriver.gain.single_ended` | 0 |
| `mute` | rfdriver | `rfdriver.mute.mute` | 1 |
| `bypass` | rfdriver | `debug.rf_tx_bypass.rfdriver` | 0 |

### ATB taps (each behind ~20 kΩ on the block)

| Block | Tap (on / off voltage) | Bound at top |
| --- | --- | --- |
| txmix | `atb_bias` (0.94 V / 0), `atb_tail` (0.79 V) | `txmix_i.atb_bias` on ATB1 code 20; others unbound |
| txsum | `atb_cm` (2.84 V / 0) | unbound |
| rfdriver | `atb_bias` (0.95 V / 0), `atb_pre` (2.62 V), `atb_cm` (pad common mode) | `atb_bias` on ATB1 code 21; others unbound |

## Results (extracted, tt / 27 °C / 3.3 V unless stated)

Corner ranges are over tt/ss/ff × 22/32 °C × 3.15/3.35 V; the worst corner is ss/32 °C/3.15 V.

| Item | Target | Result |
| --- | --- | --- |
| Mixer conversion transconductance, linear / `sat=1` | 1 mS | 1.51 / 2.72 mS at 1.00 mA |
| txsum transimpedance / input impedance at 2.44 GHz | 1000 Ω / ≤ 100 Ω | 220 Ω / 262 Ω: miss (RFT-04) |
| rfdriver voltage gain, `in` → pad, 50 mV | 5.36 V/V | 5.70 V/V |
| Matched output, linear, 0.3 V / 0.7 V DC I | 0 dBm | +5.14 / +9.51 dBm |
| Matched output, saturated (1.0 V, `sat=1`) | 0 dBm | +9.52 dBm |
| Matched SSB (61 MHz), linear 0.3 V / saturated | 0 dBm | +5.55 / +9.95 dBm; saturated image 33.4 dB, LO 39.8 dBc |
| Matched linear output (0.3 V) over corners | 0 dBm | −0.72..+8.72 dBm: miss at ss (RFT-01) |
| Matched saturated output over corners | 0 dBm | +6.88..+10.96 dBm |
| Chain AM-AM, linear mode: P1dB / Psat | — | +8.8 / +9.7 dBm |
| HE20 OFDM at +0.09 dBm mean, linear mode: EVM / ACLR / mask margin | ≤ −27 dB (MCS7) / — / ≥ 0 dB | −30.0 dB / 39.0 dB / +3.4 dB |
| Highest mean power meeting EVM and mask: MCS0–4 / MCS5 / MCS7 / MCS9 | 0 dBm | +4.66 / +4.08 / +1.50 / −2.09 dBm |
| LO quadrature skew 2 / 5 / 10 / 20 ps: image rejection; EVM at 0 dBm | — | 37.5 / 30.3 / 24.5 / 18.5 dB; −28.4 / −26.7 / −23.5 / −18.5 dB (LO-06) |
| LO white jitter 0.5 / 1 / 2 ps rms: mask margin at 0 dBm | ≥ 0 dB | +3.2 / +2.3 / −0.1 dB |
| Chain image rejection / LO suppression, ideal LO | — | 54.5 dB / 30.1 dBc (RFT-05) |
| Harmonics after the ideal balun, linear mode, 0.02–1.3 V drive | — | H2 −38..−64 dBc, H3 −45..−59 dBc |
| Saturated power control, code 1 / 4 / 8 / 15 (matched) | monotonic | −12.4 / +0.5 / +5.7 / +9.5 dBm |
| Mute isolation, matched saturated | — | 46.2 dB |
| rfdriver current: linear / saturated / zero input / mute / bypass | ≤ 61.7 mA | 52.8 / 53.4 / 58.4 / 22.8 / 1.3 mA; 49.7..56.5 mA over corners |
| Unmatched (50 Ω differential, bias-tee chokes): chain at 0.3 V | — | +0.74 dBm (−5.04..+4.53 over corners) |
| Stretch, unmatched: LO/2 1.22 GHz, LO/4 610 MHz (0.3 V) | non-gating | +9.95, +10.65 dBm |

**Stability** (RFT-09): the differential output conductance is positive from 10 MHz to 20 GHz at ss/tt/ff with
0 and 262 Ω source (minimum 0.35 mS); a kick with 22 and 100 nH feed chokes, matched and with the pad side open,
decays by at least 530× between 30–35 ns and 45–50 ns.

**Safe** (family-level extracted benches, all four blocks, LO running): reset (`en=0`, `mute=1`) static rail
current ≤ 0.03 µA at 3.3 and 3.63 V, 0–85 °C including ff; island rail at 0 V with controls low, high or
bypass: no static back-feed and no baseband source current; rail ramp to 3.63 V in reset: 7.7 µA after the ramp
(criterion ≤ 10 µA), 0.5 mA displacement peak; missing `ibias` with `en=1`: 0 mA; grounded 50 Ω peer in reset or
with the rail off: < 1 µA. Out of contract: 3.3 V DC on RF_TX with the rail off drives 4.1 mA through the
rfdriver PMOS junctions.

**Fallback**: `rf_tx_low_power_external_pa` (`bypass=1`, rfdriver amplifier off, 1.3 mA): −38.4 dBm from the
chain at 0.3 V baseband (−35.2 dBm matched, −27.9 dBm matched saturated), so an external PA needs about 38 dB
of gain. `rf_tx_external_upconverter` (mixers and txsum off, baseband out through `bb_tap`): mixer-off loading
33 fF, route not simulated end to end. Filter-bypass input (`sel_dac=1`): SSB +1.12 dBm unmatched, image
rejection 54.6 dB.

## Open items

1. **Linear output at the slow corner** misses 0 dBm at 0.3 V drive (−0.72 dBm matched); results with the
   pessimistic device-speed derate exist only in `scratch/rf-tx-d3/` and are not in the evidence files
   (RFT-01). The `nfet_06v0` cascode costs saturated power (RFT-02, accepted).
2. **Real LO not simulated.** The benches use an ideal rail-to-rail square LO; the published LO buffer delivers
   0.62–0.81 Vpp per side (`analog/timing/README.md`). TX gain, output power and LO feedthrough with the real
   LO are unverified.
3. **Package and board.** No bond-wire, package, supply-network or substrate model; the pad is a 2 Ω + 1 pF
   allocation, not the extracted pad; the match and balun are ideal parts on a board node next to the pad,
   which the COB does not offer (nearest passive on the carrier). To be requalified through the real channel
   (BRD-01).
4. **Deep n-well.** The rfdriver source followers use an isolated p-well; deep n-well is not yet confirmed
   for the run (`scratch/reviews/wafer-space-answers.md`).
5. **LO feedthrough is layout-symmetry sensitive**; top-level routing of `lo_*` and the mixer outputs needs
   separation and shielding. Saturated-mode image and LO levels suit constant-envelope modulation only (RFT-05).
6. **Observability**: only two bias taps are bound to the ATB; the evidence test stays open (INT-04).
7. **Gate stress** on the rfdriver follower and tail-switch gates slightly above 3.63 V at extreme corners
   (PAD-06).
8. **Modulation results** come from a memoryless model of the extracted AM-AM/AM-PM, not a modulated
   transistor-level transient; DAC linearity is not included (RFT-03).
9. **Not covered**: wire and via resistance (C-only extraction; IR and EM unchecked), gate resistance, noise,
   mismatch, density; `txmix_q` evidence reuses the I-cell block bench (MOD-01, MOD-16).
10. **txsum** misses its transimpedance and input-impedance targets (RFT-04).
