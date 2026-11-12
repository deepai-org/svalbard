# RF transmit family: `txmix_i`, `txmix_q`, `txsum`, `rfdriver`

> **2026-11-10 (RC-3/RC-18, RF/converters owner): rfdriver output is now 6 V-safe.** nfet_06v0 cascodes
> (960/0.7 per leg, drains on the pads, gates from 6 V drivers with 6 pF 6 V MOS decaps), the pad bypass
> switch is a pfet_06v0 in its own n-well `nwb` (10 kΩ from VDD) with an nwb-supplied gate driver, output-pair
> gates are pulled low when off, and a new `se` port selects the single-ended mode (pad_n cascode off, that
> leg into an on-chip PMOS dummy). Layout republished (DRC 0, LVS unique, KLayout 0/0, 133,269 µm²).
> Stress screen with the pads' rf-tx macro and the P2 package bench: `scratch/rfconv-owner/tx/`
> (`stress.json`, `p2b.json`).
>
> **2026-11-11 (RFT-2): reset leak fixed and evidence regenerated.** The P3C gate pull-downs fought the VDD-fed source (risk: RFT-01)
> followers (2.0–2.4 mA in reset, safe fail); the SF drains now sit on a switched header `sfd` (`SFH_a/b`,
> 2 × 640 µm, off with `pre_off`). Republished layout 135,222 µm² (DRC 0, LVS unique, KLayout 0/0). sch + ext benches,
> `tx_modulation.py` and `evidence.py` rerun: safe/clean pass for all four blocks. Extracted: matched linear +3.0 dBm
> (0.3 V) / +7.9 dBm (0.7 V), saturated +7.9 dBm, HE20 MCS7 at +0.13 dBm (EVM −27.9 dB); rfdriver 52–58.7 mA tt,
> 38.2 (ss/32/3.15) … 55.8 mA (ff). **ss/32/3.15 linear matched −5.6 dBm (< 0 dBm target)**; saturated +1.9 dBm.
> Rows below that quote older numbers are historical. `generate.py` also records `lvs_name_equivalent`, an exact
> by-name device comparison. netgen sees the PDK devices as black boxes, so the 4 binary tail slices are symmetric to it,
> and a pin-permutation result can occur by chance.

> **2026-11-12 (fork D2, RFT-09 + RFT-01): driver oscillation fixed; ss linear output at the pessimistic fT.** The extracted rfdriver had a negative differential output conductance (−0.9…−4.6 mS, 0.2–0.9 GHz, ss/ff) from same-phase
> pad→input coupling (≈6 fF/leg through the off bypass PMOS, 2–3 fF pad→p1/p1b): with the ~260 Ω txsum source and a B17
> ≥22 nH feed choke it oscillated (3–8 V, ss/ff). Fix: T bypass switch `BYPA` (pad→`bm`) + `BYPB` (`bm`→in, 4 µm fingers)
> + `BSH` (nfet_06v0, `bm`→VSS while bypass=0), pad-side halves in the pad-load row, device gap 0.8 µm. No port change.
> 97,609 µm² (≤ 98,100); Magic DRC 0, LVS unique + name-equivalent, KLayout 0 / antenna 0. Re(Ydiff) > 0 at ss/tt/ff (source
> 0 / 262 Ω); kicks decay ≥ 45× at the pessimistic package (review, scratch/review-rfd2), fast end ≥ 380×. tt: matched lin +5.14 dBm (was 4.49), sat +9.52, MCS7 max mean +1.50 dBm
> (was +2.22), mute isolation 46.2 dB (41.8), LO suppression 30.1 dBc (28.9); bypass path −5.9 dB (−26.1 dBm drv_bypass);
> stress screens unchanged (pulse/HBM/func identical to fork N). Pessimistic derate (Rg 200 Ω/10 µm, fT 11 / 5.5 GHz),
> ss/32/3.15: *superseded by the review follow-up below (that derate under-shot fT; numbers were optimistic).* Max rfdriver current 60.16 mA
> (`drv_a600`, standalone driver overdriven at 0.6 V; the published `drv_a*` decks were broken before and read −50 dBm / 25 mA),
> chain max 58.4 mA. Work: `scratch/rf-tx-d2/`.
>
> **2026-11-12 (review follow-up A–F, RFT-01/RFT-09).** Derate recalibrated so single-device ss/32 °C fT is exactly
> 11.0 GHz (nfet_03v3) / 5.5 GHz (nfet_06v0) (`scratch/rf-tx-d3/ftcal.json`; the old one gave 12.1 / 4.57), Rg 200 Ω/10 µm.
> ss/32/3.15 extracted chain, linear (sat=0) / saturated (sat=1):
> published board (Q30, 1 dB, 200:50): 0.3 V −8.5 dBm, P1dB −0.2 dBm, Psat −0.05 dBm — **0 dBm CE missed by 0.05–0.2 dB**;
> pessimistic board (Q20, 2 dB balun, pad C +30 %, bond 1.5/3.7 nH/leg, match re-derived incl. balun ratio 50:50 / 400:50):
> 0.3 V −7.3/−7.5 dBm, P1dB +0.85/+0.70 dBm, Psat +1.05/+0.87 dBm, 0 dBm linear at 0.71/0.74 V BB → **CE/linear margin
> +0.7…+0.9 dB only with the re-derived board match** (the 200:50 balun mismatches the ~700 Ω pad). HE20 MCS7 max mean
> −5.6…−6.8 dBm (≥ −10 dBm OFDM target met). SSB at ss: linear 0.7 V IR 35–39 dB, LO 20–21 dBc; saturated IR 28.4–28.7 dB
> (**< 35 dB**), LO 37–38 dBc. bbfilter_i TX direction at ss (ext, 1 pF/leg txmix load): IM3 −53.2 / −50.7 dBc at 0.65 / 0.76 V
> diff pk (−34.5 at 1.0 V). Stability is now a bench + evidence test (`stab_*`, `tests.stable`, fails on the pre-fix
> netlist: −4.56 mS, kick ×0.9). rfdriver max current 61.69 mA (ff/22 °C/3.35 V, overdriven, `imax.json`) → allocation 61.7 mA.
>
Transistor-level 2.4 GHz transmit path:
`bbfilter (TX direction, analog/rf_rx) → txmix_i/q → txsum → rfdriver → RF_TX pad`.
TX reconstruction filtering is in the shared `bbfilter_i/q`; each mixer also
has a selectable direct DAC input (filter bypass) so TX→RX loopback works while
the filter serves RX. gf180mcuD 3.3 V devices and poly resistors only (no
inductors, no capacitors); one 10 µA bias input per block; enables decoded by
small static CMOS gates on the island rail. Nothing here is silicon-qualified.

## Files and how to run

| File | Content |
| --- | --- |
| `circuits.py` | single source of all netlists; writes `<block>.spice` (top cell `pt_<block>`) |
| `layoutlib.py` | row/channel Magic generator (PCells, M2–M5 routing), DRC, extraction, Netgen LVS |
| `generate.py`, `generate_<block>.py` | per-block placement/routing options; publish to `generated/` |
| `gds_export.py` | GDS re-export with Magic 8.3.678 (HRES/RES_MK marker count) + KLayout GF180 DRC |
| `simulate.py`, `run_benches.py` | ngspice benches: block, chain, matched, corners, safety, loading, stretch |
| `evidence.py` | writes `generated/<block>-evidence.json` |
| `generated/` | `<block>.gds/.mag/.ext.spice`, `-drc.txt`, `-lvs.txt`, `-layout.json`, `-gds-export.json`, `-klayout-drc.lyrdb`, `-evidence.json`, `rf_tx-sim-{ext,sch}.json` |

`./run_rf_tx.sh` regenerates everything (~10 min). Images, all `--network none`,
≤3 CPUs / 6 GB: Magic DRC, extraction and Netgen LVS in
`svalbard/librelane-gf180-canary:2026.08` (`sha256:b60278092f08…`, Magic
8.3.623, Netgen 1.5.316); GDS export (Magic 8.3.678, which writes the HRES 62/0
marker the canary omits), KLayout DRC and ngspice in
`hpretl/iic-osic-tools@sha256:89641950…` (local `sha256:bd7a702b…`). Host:
Python 3 + NumPy. Raw work: `scratch/rf_tx/`.

## Circuits

| Block | Topology | Current | Area µm² (ceiling) |
| --- | --- | --- | --- |
| `txmix_i/q` | Double-balanced Gilbert upmixer: NMOS transconductor with 600 Ω `ppolyf_u_1k` degeneration, two 0.5 mA tails from the 10 µA diode, 4 NMOS commutators, open-drain current outputs. NMOS input switches select `bb_*` (`sel_dac=0`) or `dac_*` (`sel_dac=1`); `sat=1` shorts the degeneration (saturated mode). | 1.00 mA (drawn through txsum loads) | 21,788 (27,300) |
| `txsum` | I/Q mixer drains joined at `out_*`; ~300 Ω `ppolyf_u` load per leg to a PMOS header (open when `en=0`); outputs clamp to VSS when off. | none of its own (carries 2.0 mA) | 4,165 (5,600) |
| `rfdriver` | Two pre-amps (2.8 mA each), NMOS followers (2 × 2.2 mA), output pair (W = 480 µm/side) with binary tail slices 6/12/24/48 (18 mA at code 15), ~100 Ω `ppolyf_u` source resistor per leg to a PMOS header; PMOS bypass switches `in_* → pad_*`; weak pad clamps when off. | chain tt: 25.7 mA linear, 25.5 saturated, 27.9 zero input, 10.2 muted, 0 bypass (budget 28.9) | 78,468 (98,100) |

## Interfaces

- **LO** (`lo_p/n`): differential rail-to-rail square, 2.44 GHz, 50 % duty,
  DC-coupled to the commutator gates; Q mixer LO delayed T/4. Load per line:
  two W = 20 µm gates + ~22 fF wiring. A 2.5 V LO high costs 0.1 dB.
- **Baseband** (`bb_*` from bbfilter, `dac_*` from the DAC): voltage-mode,
  1.65 V CM, DC-coupled, no DC load; ~136 fF selected, ~31–34 fF off/unselected.
  The DAC supplies its own I-to-V load. Linear to ±0.35 V pk diff, compresses
  above ~0.7 V.
- **Bias**: `ibias` 10 µA into an NMOS diode (~0.95 V); the diode stays
  connected (sinks 10 µA whenever driven), mirror gates are switched.
- **RF_TX pad / board**: pad modelled as 2 Ω + 1 pF per leg; board must be
  DC-blocked (balun). Pad CM ~2.4 V enabled. Recommended network
  (`simulate.design_match`, tt pad admittance G = 8.8 mS, C ≈ 0.99 pF): ~13.9 nH
  shunt across RF_TX_P/N, 2 × 1.85 nH series into a 50 Ω differential port,
  1:1 balun. Simulated with inductor Q = 30, balun loss not included; a plain
  50 Ω differential load costs 1.4 dB.
- **Supplies**: `VDD` = `VDD_RF_SW` 3.3 V, `VSS`.
- **Ports**: Metal5 labels on each block's top edge.

### Controls (active high, 3.3 V core-domain, safe at 0 V with the island off)

| Port | Block | Proposed register source | Reset |
| --- | --- | --- | --- |
| `en` | txmix_i/q | `txmix_{i,q}.enable` AND state ≠ off | 0 |
| `sel_dac` | txmix_i/q | new field (`txmix.input_select` / `debug.tx_filter_bypass`) | 0 |
| `sat` | txmix_i/q | new field `txmix.sat_mode` (1 = constant-envelope; 0 = linear/OFDM) | 0 |
| `en` | txsum | `txsum.enable` AND state ≠ off | 0 |
| `en` | rfdriver | `rfdriver.state` ≠ off | 0 |
| `se` | rfdriver | `rfdriver.se` (D-TX-2 single-ended output) | 0 |
| `mute` | rfdriver | `rfdriver.mute` | 1 |
| `g3..g0` | rfdriver | `rfdriver.gain.code[7:4]` (default 206 → 12) | 1100 |
| `bypass` | rfdriver | `debug.rf_tx_bypass` | 0 |

### ATB taps (each behind ~20 kΩ; `atb_tap` cells added at integration)

| Block | Taps |
| --- | --- |
| txmix | `atb_bias` (tail mirror gate, 0.94 V on / 0 off), `atb_tail` (transconductor source, 0.79 V) |
| txsum | `atb_cm` (summing-node CM, 2.84 V on / 0 off) |
| rfdriver | `atb_bias` (0.95 V), `atb_pre` (pre-amp 2 CM, 2.82 V), `atb_cm` (pad CM) |

## Results (extracted, tt / 27 °C / 3.3 V unless stated)

Source: `generated/rf_tx-sim-ext.json` and `generated/<block>-evidence.json`.
"Matched" = board network: per-leg chokes (Q=30) from each pad to the rf_tx
island rail that resonate the pad susceptance and DC-feed the output stage,
DC blocks, an ideal 200:50 Ω balun and a 1.0 dB resistive pad for the balun's
insertion loss (assumed: a 2.45 GHz 200:50 Ω chip balun with centre-tap DC feed,
datasheet-class loss 0.6–1.0 dB), power into 50 Ω. Unmatched benches use 20 nH
bias-tee chokes and a DC-blocked 50 Ω differential load. Modulation results:
`tx_modulation.py` → `generated/rf_tx-modulation.json`.

| Item | Target | Achieved | Verdict |
| --- | --- | --- | --- |
| Magic DRC / Netgen LVS / KLayout DRC, all blocks | 0 / unique / 0 | 0 / unique / 0 | pass |
| Mixer conversion gm, linear / sat=1 | 1 mS | 1.51 / 2.72 mS, 1.00 mA | pass |
| Mixer DAC input (filter bypass) | works | 1.51 mS | pass |
| txsum transimpedance / input impedance, 2.44 GHz | 1000 Ω / ≤ 100 Ω | 220 Ω / 262 Ω | miss (risk: RFT-04) |
| rfdriver gain (summed_rf → pad, 50 mV, bias tee into 50 Ω) | 5.36 V/V | 5.24 V/V (was 1.68) | ≈ target |
| Matched SSB, linear (0.3 V I/Q, 61 MHz), after 1 dB balun loss | 0 dBm | +3.7 dBm (was −5.6, balun loss excluded) | pass |
| Matched SSB, saturated (1.0 V I/Q, sat=1), after balun loss | 0 dBm | +8.05 dBm (image −30 dBc) | pass |
| Chain AM-AM (CW, linear mode), after balun loss: P1dB / Psat | — | +3.8 / +5.9 dBm | — |
| Driver alone into the board: Psat | — | +9.0 dBm | — |
| HE20 64QAM OFDM at 0 dBm mean (after balun): EVM / ACLR / mask margin | ≤ −27 dB (MCS7) / — / ≥ 0 | −22.8 dB / 29.9 dB / +0.1 dB (sat=1 mode: −22.6 / 29.9 / +1.7) | MCS0–5 pass, **MCS7 miss by ~1 dB** (−1.0 dBm max) (risk: RFT-01) |
| Harmonics after ideal balun, 0.3–1.0 V drive | — | H2 −41…−52 dBc, H3 −52…−66 dBc | recorded (needs board LPF for FCC 15.247) (risk: EMI-02) |
| LO quadrature skew 2 / 5 / 10 / 20 ps (transistor level) | — | IRR 36 / 29 / 23 / 17 dB; EVM at 0 dBm −22.5 / −21.9 / −20.3 / −16.8 dB | ≤5 ps needed (risk: LO-06) |
| LO white jitter 0.3 / 1 / 2 ps rms | — | EVM unchanged (compression-limited); mask margin +0.2 / −0.5 / −2.1 dB | ≤0.5 ps needed |
| Chain image rejection / LO suppression, matched linear (ideal LO) | — | 48.9 dB / 33.9 dBc | — |
| Saturated power control, code 1/4/8/15 (matched) | monotonic | see `rf_tx-sim-ext.json` match_code*_sat | pass |
| Matched linear / saturated vs corners (12 env) | 0 dBm | −2.8..+5.0 / +4.5..+6.1 dBm (worst ss/32 °C/3.15 V) | ss linear marginal |
| rfdriver current incl. board feed, code 15 | 28.9 mA (old allocation) | 53–59 mA tt; 41–56 mA over corners | **budget raised** (interface-changes.md) (risk: PWR-09) |
| Stretch: LO/2 1.22 GHz / LO/4 610 MHz, unmatched (0.3 / 0.7 V) | — | +1.4 / +2.3; +2.9 / +3.1 dBm | non-gating |

## Four tapeout tests

| Test | txmix_i/q | txsum | rfdriver |
| --- | --- | --- | --- |
| safe | pass | pass | pass |
| clean | pass | pass | pass |
| observable | open | open | open |
| fallback | open | open | pass |

- **safe** (family-level extracted benches, all four blocks, LO running): reset
  (en=0, mute=1) < 0.03 µA per block at 3.3/3.63 V, 0–85 °C incl. ff; island
  rail at 0 V with controls low/high/bypass: no static backfeed, no baseband
  source current; reset rail ramp to 3.63 V: 1.49 µA mean 50–200 ns after the
  ramp (criterion ≤ 10 µA), 109 µA displacement peak; missing ibias → 0 mA;
  bypass with en=1 → output stage 0 mA; grounded 50 Ω peer in reset or rail off
  → 0 mA. Board contract: the RF_TX load must be DC-blocked (the DC feed comes from the island rail through the balun centre tap / chokes) (enabled into a DC-coupled
  grounded peer: 29 mA into the peer; 3.3 V behind 50 Ω with rail off: 90 mA
  through rfdriver PMOS junctions, out of contract). Off states: mixer current
  outputs unclamped (tail off, gm gates clamped), txsum clamps to VSS, rfdriver
  pads held by weak NMOS clamps. (risk: BRD-01)
- **clean**: Magic DRC 0, Netgen unique, KLayout GF180 DRC 0 on the 8.3.678 GDS
  with HRES 62/0 on every `ppolyf_u_1k`. `ppolyf_s/u` resistors are drawn
  without their PCell guard ring (the ring trips KLayout PP.2); their substrate
  terminal is the VSS-tied p-substrate, LVS-confirmed. Extracted nominal runs
  show upconversion, summation, drive and bypass.
- **observable: open** — ATB nodes simulated on/off, but `atb_tap` cells, mux
  codes and register fields are not assigned. No clocks or status bits. (risk: INT-04)
- **fallback**: rfdriver route `rf_tx_low_power_external_pa` implemented and
  simulated (−24.8 dBm best case → external PA needs ~25 dB gain). txmix/txsum
  route `rf_tx_external_upconverter` depends on the `bb_tap` observe path
  (rf_rx) and stays open; disabled-mixer loading on the baseband node 31 fF;
  filter-bypass input demonstrated in the chain (SSB via `dac_*`: −7.0 dBm
  unmatched). (risk: BRD-01)

Evidence currency: all `source_hashes` in `generated/*-evidence.json` match the
current sources.

## Limitations and open items

1. **Output power** (2026-11-09 rework): the driver is now DC-fed from the
   board (balun centre tap or chokes to the rf_tx island rail) instead of the
   on-chip 4 x 400 Ω resistive feed, has a third pre-amplifier, stronger source
   followers and a doubled output stage. HE20 at 0 dBm mean meets MCS0–5 EVM and
   the mask; MCS7 reaches −1.0 dBm. Remaining loss is in the extracted
   chain ahead of the driver (driver alone +9 dBm Psat, chain +5.9 dBm).
   Historical note (old design): linear mode −5.6 dBm SSB tt (−9.6 dBm ss/3.15 V);
   saturated −0.1 dBm tt (−2.8 dBm ss). Limited by gm/C at 2.44 GHz without
   inductors and by wiring capacitance (~4 dB vs schematic). Top-level wiring
   will cost more; board L-match values depend on unmodelled bond-wire/package
   parasitics and must be tuned on the bench. (risk: RFT-01)
2. **LO feedthrough is layout-symmetry sensitive** (~5 fF asymmetry between LO
   and mixer-output routing can collapse LO suppression); top-level routing of
   `lo_*` and `out_*` must keep separation and shielding. (risk: RFT-05)
3. **Bypass route** works but is weak (−25 dBm at best).
4. **Pad bias / stress**: pads now sit at the island rail (~3.3 V) with peaks
   to ~4.1 V; output-device Vds stays ≤ ~3.5 V. The rftxpad stress-safe clamp
   (2.1 V onset at ff) is incompatible and must be replaced (interface-changes.md).
   The bypass route with the board feed passes ~1.6 mA DC from the feed into txsum. (risk: ESD-04)
5. **Saturated-mode spectrum**: image ~33 dB and LO ~38 dB down: fine for
   GFSK / O-QPSK / LoRa, not OFDM. (risk: RFT-05)
7. **Gate resistance not in the benches** (PDK rgatemod=0). Estimate
   (2026-11-10, not simulated): 20 µm fingers at 120–300 Ω each
   (60–150 Ω per 10 µm), Cgg ≈ 40 fF (L 0.28) / 64 fF (L 0.5), give gate poles
   at 13 / 8 GHz, i.e. 0.15–0.36 dB per stage and ≤ ~1 dB over 4 stages at
   2.45 GHz. Linear output (+3.7 dBm) keeps margin over 0 dBm. The MCS7 EVM gap
   (~1 dB) may grow. An Rg-annotated extracted rerun is open. (risk: MOD-01)
6. **txsum** misses its transimpedance and input-impedance targets (a
   low-impedance current summer does not fit 3.3 V headroom with a
   rail-to-rail LO). (risk: RFT-04)
7. Not covered: wire/via resistance (C-only extraction; ~9 mA per leg through
   single-PCell-wide via stacks, IR/EM unchecked), package/bond-wire/supply/
   substrate models, noise, mismatch/Monte Carlo, EVM, spectral mask; LO,
   baseband and DAC sources ideal; block-level DRC only (no antenna/density, no
   integrated DRC/LVS). `txmix_q` evidence reuses the I-cell block bench (both
   cells exercised in the chain). (risk: MOD-16)
