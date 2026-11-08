# Wired-TX family (`analog/wired_tx`)

Serializer, pre-driver gating and tail-bias DACs (`pt_wiredtx`), the `tmds`
configuration, the `wtx_ext_rx` receiver instance and the USB HS bias DAC
(`pt_wtx_hsbias`).  Ring phases come from timing's shared `pt_pll_ring`.
Nothing here is qualified; numbers are extracted (Magic C) unless noted, and
`generated/*-evidence.json` is the record of truth.

| Block | Layout | DRC (Magic / KLayout) | LVS | Extracted function | Four-test (safe / clean / observable / fallback) |
| --- | --- | --- | --- | --- | --- |
| `wiredtx` (`pt_wiredtx`) | 335.8 × 591.7 µm = 0.199 mm² (allocation 0.30), 1427 devices | 0 / 0 | unique | 0.96 Gb/s half rate (ring 480 MHz): 0 errors at tt and all 12 corners; 1.25 Gb/s passes tt/ff, fails ss | pass / pass / pass / pass |
| `tmds` | configuration of `wiredtx` + pad TMDS branch | (wiredtx) | (wiredtx) | 1.25 Gb/s into 50 Ω pull-ups: eye 955 mV / 663 ps, 1.16 Vpp diff | pass / pass / pass / pass |
| `wtx_ext_rx` | instance of timing's `pt_diff_clk_rx` (`wtx_ext_rx.spice`) | timing | timing | ideal DX: 1 Gb/s, 0 errors, eye 388 mV / 965 ps at the pad; through the extracted receiver: 5/43 errors at 0.5 Gb/s (start-up), no output at 2 Gb/s | pass / pass / pass / n/a |
| `usb_hs_bias` (`pt_wtx_hsbias`) | 125.8 × 76.0 µm = 9,552 µm², 53 devices | 0 / 0 | unique | 0–0.58 V full scale (tt), monotonic at all corners, settles to 1 LSB in 0.47 µs | pass / pass / open / n/a |

**Achieved line rates after extraction (tt):** quarter rate none (1.92 Gb/s
fails; the schematic passes 2.5 Gb/s); half rate 0.96–1.25 Gb/s (1.62 fails);
full rate 0.48 Gb/s (0.81 fails).  The gap is routing capacitance of the
generic layout style.

**Evidence currency:** `cells.py`, `wiredtx.spice`, `wtx_ext_rx.spice`,
`layoutgen.py`, `sim_integration.py`, `run_all.py` and `evidence.py` changed
after every evidence file.  The `wiredtx` layout in `generated/` was rebuilt
from the current netlist (1427 devices, DRC 0, KLayout 0, LVS unique); the
evidence and simulations describe the previous netlist (1403 devices,
0.200 mm²).  Rerun `./run_wired_tx.sh sims` and `./run_wired_tx.sh evidence`.

## Reproduce

```
./run_wired_tx.sh                 # all stages
./run_wired_tx.sh layout          # netlist (cells.py) + layout + DRC/LVS + GDS/KLayout
./run_wired_tx.sh sims [job...]   # extracted simulations (all, or named jobs)
./run_wired_tx.sh evidence        # generated/*-evidence.json and the table below
```

Magic layout/DRC/extraction and Netgen LVS run in
`svalbard/librelane-gf180-canary:2026.08`; GDS export (Magic 8.3.678),
KLayout DRC and ngspice 43 in `hpretl/iic-osic-tools@sha256:8964…`; the
pad-integration decks use the pads family's patched ngspice-47
(`scratch/pad-ngspice47`, recorded in `analog/pads/generated/simulator-build.json`).
All containers `--network none`; raw output in `scratch/wired_tx/`.

| File | Role |
| --- | --- |
| `cells.py` | Single source of the transistor-level cells; writes `wiredtx.spice` and `hsbias.spice` |
| `layoutgen.py` | Serpentine-row gencell placement, fixed-direction metal (m2 jogs, m3 risers, m4 tracks, m5 trunks); can place compact cells as macros |
| `tools.py` | Docker wrappers (Magic, Netgen, KLayout, ngspice) |
| `sim_wiredtx.py`, `sim_integration.py`, `sim_static.py`, `sim_hsbias.py` | Serializer, pad-integration, static/safety and HS-bias benches |
| `run_all.py`, `evidence.py`, `run_wired_tx.sh` | Orchestration and evidence |
| `cells_fastpath_wip.py`, `wtx_fast.py` | Unconverged quarter-rate fast-cell path (not in the netlist; see Open items) |
| `generated/mag/`, `generated/mag_hsbias/` | Magic hierarchy (top + primitive cells) for `pt_wiredtx` and `pt_wtx_hsbias` |

## Architecture

```
 D0..D19 (2 line words, D0 first) --INV--> 4 x 5:1 parallel-load shift registers   (register clock FCK, period 4 UI)
 WORD_CLK (bit/20) <-- divide-by-5 (load pulse LD, WORD_CLK)                         |
                                       retime flops on FCK fall (A0..3) / FCK rise (B1..3, C3)
                                                      |
                     window generator (MODE_H/MODE_F) -> 4 window pairs (WAk, WBk), k = UI within the period
                                                      |
             4:1 NAND3/NAND4 window muxes: main Y/YB = (A0,A1,B2,B3), postcursor DP/DPB = (C3,A0,B1,B2)
                                                      |
  DX (pt_diff_clk_rx on WTX_EXT_P/N) -> break-before-make select (SER vs EXT) -> branch gating
        CMD_MAIN_P/N = data & EN_MAIN, CMD_TMDS_P/N = data & EN_TMDS, CMD_POST_P/N = postcursor & EN_POST & SER
                                                      |
                  pads: tx_steering_buffer (x6) -> tx_protected_pad selector gates / tails
  IBIAS (10 uA) -> mirror -> three 8-bit PMOS DACs -> MAIN_BIAS / POST_BIAS / TMDS_BIAS (pad tail gates)
```

* **Bits per ring cycle:** quarter (default, 4 bits, windows from the four
  phases), `MODE_H` half (2 bits, PH0/PH180 and a retimed toggle), `MODE_F`
  full (1 bit, 2-flop Johnson counter on PH0); `MODE_F` wins.  All modes give
  the same register clock (4 UI) and window set.  Ring 480–810 MHz covers
  1.92–3.24 / 0.96–1.62 / 0.48–0.81 Gb/s.  Ring phases are gated by `SER`
  before the window selects, so nothing downstream toggles with the
  serializer off.
* **Postcursor:** a second 4:1 mux gives the main stream delayed by one UI
  (bit-exact), wired for de-emphasis.
* **Polarity:** logical 1 steers the MAIN/TMDS tail to the N leg, so
  V(PAD_P) > V(PAD_N).
* **Tail-bias DACs** (`wtx_idac2` MAIN/POST, `wtx_idac1` TMDS): 10 µA →
  mirrors → 8 binary PMOS sources (5 µA LSB) into an NMOS diode 1/16 of the
  pad tail; tail LSB ≈ 83 µA.  MAIN 109 → 9.05 mA, TMDS 102/125 → 8.43/10.32
  mA, 255 → 21.05 mA.
* **`pt_wtx_hsbias`** (USB HS `HS_PBIAS`, gate of 28 pfet 20/1): 10 µA
  reference, eight binary PMOS sources (~1.25 µA unit) into an NMOS triode
  load (gate = EN) to VSS.  `EN=0` turns the sources off and pulls
  `HS_PBIAS` to VDD; no static current.  Ports `IBIAS EN C0..C7 HS_PBIAS VDD
  VSS`; HS_PBIAS ≈ code × 2.3 mV at tt, ±20 % over PVT (per-board
  calibration).

## Ports (`pt_wiredtx`)

| Port | Dir | Meaning / source |
| --- | --- | --- |
| `VDD`, `VSS` | supply | `VDD_WIRED_SW` (3.3 V switched island), ground |
| `WTX_PH0/90/180/270` | in | ring phases via the clockmux (stopped = PH0=PH90=0, PH180=PH270=1) |
| `MODE_H`, `MODE_F` | in | 2 / 1 bits per ring cycle (both 0 = 4); from a 2-bit rate field (0 quarter, 1 half, 2 full, 3 illegal); change only while stopped |
| `D0..D19` | in | 20-bit double word from `rtl/pt_pattern.sv`; D0 first on the line |
| `WORD_CLK` | out | bit rate / 20 (40 % duty) for the word source and `WCLK_OBS` |
| `SER_EN` | in | `wiredtx.state.state == active` and not `debug.wtx_ext`; releases the counters from reset |
| `WTX_EXT` | in | `debug.wtx_ext.enable` |
| `DX` | in | `pt_wtx_ext_rx` DX (receiver `OUTN`, legs swapped) |
| `EN_MAIN`, `EN_POST`, `EN_TMDS` | in | branch enables from the pads `interlock` cell |
| `MAIN_CODE[7:0]`, `POST_CODE[7:0]`, `TMDS_CODE[7:0]` | in | `wiredtx.config.current_code` (109), `wiredtx.config.postcursor_code` (0), `tmds.config.current_code` (102) |
| `IBIAS` | in | 10 µA from the wired-island bias distributor, switched in while any EN_* is high |
| `ISLAND_OFF` | in | core-domain high while the island is off: clamps every CMD output and tail bias to VSS |
| `CMD_MAIN_P/N`, `CMD_POST_P/N`, `CMD_TMDS_P/N` | out | to the pads `tx_steering_buffer` inputs |
| `MAIN_BIAS`, `POST_BIAS`, `TMDS_BIAS` | out | pad tail gates |
| `WTX_EXT_DATA` | out | buffered DX → status bit `wtx_ext_data` |
| `ATB_NBIAS`, `ATB_PBIAS` | out | ATB taps (reference diode, MAIN DAC PMOS gate) → `atb_tap` (node 26 `wiredtx_bias`) |

All control and data inputs see MOS gates only, so a core-domain driver that
is high while the island is off draws no current (simulated).

**Word-load timing (`integration/pt_wired_tx.sdc`):** the word source
launches on `WORD_CLK` rising; the shift registers load three register
periods later, i.e. `WORD_CLK` falling + `T_word/5` − ~0.4 ns buffer delay;
setup ≈ 0.5 ns, hold ≈ 0.3 ns about that edge.  Constraining setup to
`WORD_CLK` falling is conservative by `T_word/5` and correct for hold.
Latency word launch → line ≈ 23 bits.

**`wtx_ext_rx` requirement:** the AC-coupled source sends ≥ 128 balanced bits
(e.g. 1010) before payload (receiver baseline settling).

## Ownership

| Item | Owner |
| --- | --- |
| Serializer, final mux, pre-driver gating, ext-data select, tail-bias DACs, HS bias DAC | this family |
| Steering buffers, pad tails/selectors, cascodes, terminations, detect, interlock, protection, USB HS/FS/LS drivers | `analog/pads` |
| Ring PLL, phases, clockmux, word divider `pt_wordclk`, `pt_diff_clk_rx` | `analog/timing` |
| Pattern generator/checker (`rtl/pt_pattern.sv`), mode decode, SER_EN gating | `rtl` |

## Results

All runs are in `generated/wiredtx-evidence.json` (`performance_vs_target`)
and `generated/wiredtx-sims.json`.  Rows marked `(rev1)` were simulated on an
earlier netlist (before the reset-flop pull-up fix that removed ~2 mA reset
current) and were not repeated.  The table between the markers is
regenerated by `evidence.py`.

<!-- RESULTS:BEGIN (generated by evidence.py) -->
| Run | Rate | Bits/ring cycle | Corner | Result | Detail |
| --- | --- | --- | --- | --- | --- |
| nominal | 1.25 Gb/s | 2 | typical 27 C 3.3 V | pass | 0 errors / 60 bits, CMD jitter 301.3 ps pp, post mism. 0 |
| schematic_q2g5 (rev1) | 2.5 Gb/s | 4 | typical 27 C 3.3 V | pass | 0 errors / 60 bits, CMD jitter 112.8 ps pp, post mism. 0 |
| sweep_4_1.92 (rev1) | 1.92 Gb/s | 4 | typical 27 C 3.3 V | FAIL | 4 errors / 60 bits, CMD jitter 442.6 ps pp, post mism. 10 |
| sweep_4_2.5 (rev1) | 2.5 Gb/s | 4 | typical 27 C 3.3 V | FAIL | 20 errors / 60 bits, CMD jitter 292.2 ps pp, post mism. 15 |
| sweep_4_2.97 (rev1) | 2.97 Gb/s | 4 | typical 27 C 3.3 V | FAIL | 24 errors / 61 bits, CMD jitter 138.3 ps pp, post mism. 8 |
| sweep_2_0.96 (rev1) | 0.96 Gb/s | 2 | typical 27 C 3.3 V | pass | 0 errors / 61 bits, CMD jitter 269.6 ps pp, post mism. 0 |
| sweep_2_1.62 | 1.62 Gb/s | 2 | typical 27 C 3.3 V | FAIL | 15 errors / 60 bits, CMD jitter 535.5 ps pp, post mism. 13 |
| sweep_1_0.48 | 0.48 Gb/s | 1 | typical 27 C 3.3 V | pass | 0 errors / 60 bits, CMD jitter 483.1 ps pp, post mism. 0 |
| sweep_1_0.81 (rev1) | 0.81 Gb/s | 1 | typical 27 C 3.3 V | FAIL | 15 errors / 61 bits, CMD jitter 363.1 ps pp, post mism. 30 |
| corner_typical_22_3.15 (rev1) | 1.25 Gb/s | 2 | typical 22 C 3.15 V | pass | 0 errors / 60 bits, CMD jitter 303.7 ps pp, post mism. 0 |
| corner_typical_22_3.35 (rev1) | 1.25 Gb/s | 2 | typical 22 C 3.35 V | pass | 0 errors / 60 bits, CMD jitter 275.3 ps pp, post mism. 0 |
| corner_typical_32_3.15 (rev1) | 1.25 Gb/s | 2 | typical 32 C 3.15 V | pass | 0 errors / 60 bits, CMD jitter 337.1 ps pp, post mism. 0 |
| corner_typical_32_3.35 (rev1) | 1.25 Gb/s | 2 | typical 32 C 3.35 V | pass | 0 errors / 60 bits, CMD jitter 281.8 ps pp, post mism. 0 |
| corner_ss_22_3.15 (rev1) | 1.25 Gb/s | 2 | ss 22 C 3.15 V | FAIL | 13 errors / 61 bits, CMD jitter 797.1 ps pp, post mism. 19 |
| corner_ss_22_3.35 (rev1) | 1.25 Gb/s | 2 | ss 22 C 3.35 V | FAIL | 4 errors / 61 bits, CMD jitter 532.8 ps pp, post mism. 9 |
| corner_ss_32_3.15 (rev1) | 1.25 Gb/s | 2 | ss 32 C 3.15 V | FAIL | 15 errors / 60 bits, CMD jitter 341.0 ps pp, post mism. 15 |
| corner_ss_32_3.35 (rev1) | 1.25 Gb/s | 2 | ss 32 C 3.35 V | FAIL | 5 errors / 61 bits, CMD jitter 476.9 ps pp, post mism. 10 |
| corner_ff_22_3.15 (rev1) | 1.25 Gb/s | 2 | ff 22 C 3.15 V | pass | 0 errors / 61 bits, CMD jitter 243.3 ps pp, post mism. 0 |
| corner_ff_22_3.35 (rev1) | 1.25 Gb/s | 2 | ff 22 C 3.35 V | pass | 0 errors / 61 bits, CMD jitter 224.0 ps pp, post mism. 0 |
| corner_ff_32_3.15 (rev1) | 1.25 Gb/s | 2 | ff 32 C 3.15 V | pass | 0 errors / 61 bits, CMD jitter 248.4 ps pp, post mism. 0 |
| corner_ff_32_3.35 (rev1) | 1.25 Gb/s | 2 | ff 32 C 3.35 V | pass | 0 errors / 61 bits, CMD jitter 228.1 ps pp, post mism. 0 |
| int_serial_h1g25 | 1.25 Gb/s | 2 | tt 27 C 3.3 V | pass | eye 304.7 mV / 633.8 ps, 594.9 mVpp diff, 0 errors / 60 bits |
| int_tmds_h1g25 | 1.25 Gb/s | 2 | tt 27 C 3.3 V | pass | eye 955.0 mV / 663.3 ps, 1159.3 mVpp diff, 0 errors / 60 bits |
| int_tmds_q2g97 | 2.97 Gb/s | 4 | tt 27 C 3.3 V | FAIL | eye 1.5 mV / 77.0 ps, 1532.2 mVpp diff, 20 errors / 59 bits |
| int_serial_q2g5 | 2.5 Gb/s | 4 | tt 27 C 3.3 V | FAIL | eye 0.5 mV / 24.1 ps, 772.3 mVpp diff, 21 errors / 60 bits |
| int_stretch_5g_lossy (rev1) | 0 Gb/s | - | tt 27 C 3.3 V | FAIL | WORD_CLK not running |
| ext_ideal_1g | 1 Gb/s | - | tt 27 C 3.3 V | pass | eye 387.7 mV / 964.6 ps, 484.0 mVpp diff, 0 errors / 41 bits |
| ext_rx_0g5 | 0.5 Gb/s | - | tt 27 C 3.3 V | FAIL | eye 370.2 mV / 102.3 ps, 454.5 mVpp diff, 5 errors / 43 bits |
| ext_rx_2g | 2 Gb/s | - | tt 27 C 3.3 V | FAIL | no transitions |
| ext_handover | - | - | tt 27 C 3.3 V | pass | SER off -> EXT on gap 3.35 ns, overlap samples 0 |
| dac_tt | - | - | tt 27 C 3.3 V | data | MAIN code 109: 9.05 mA, TMDS 102/125: 8.43/10.32 mA, 255: 21.05 mA |
| quiescent_tt | - | - | typical 27 C 3.3 V | data | I(VDD) avg 11.053 mA, max CMD 0.000105 V, max bias 0.0158 V |
| quiescent_ff_85_3v63 | - | - | ff 85 C 3.63 V | data | I(VDD) avg 14.649 mA, max CMD 9.5e-05 V, max bias 0.0159 V |
| quiescent_stopped_tt | - | - | typical 27 C 3.3 V | data | I(VDD) avg 0.000 mA, max CMD 1.51e-09 V, max bias 4.99e-08 V |
| quiescent_stopped_ff_85_3v63 | - | - | ff 85 C 3.63 V | data | I(VDD) avg 0.001 mA, max CMD 4.18e-08 V, max bias 1.04e-07 V |
| unpowered_tt | - | - | typical 27 C in 3.3 V | pass | rail back-feed 1.0359e-123 A, max output 7.08e-129 V |
| unpowered_ff_85_3v63 | - | - | ff 85 C in 3.63 V | pass | rail back-feed 4.12375e-25 A, max output 3.58e-28 V |
| ramp_tt | - | - | typical 27 C | pass | max CMD 0.238 V, max bias 0.348 V, peak I 0.15 mA |
| ramp_ff_85_3v63 | - | - | ff 85 C | pass | max CMD 0.129 V, max bias 0.25 V, peak I 0.12 mA |
| nominal_0g96 | 0.96 Gb/s | 2 | typical 27 C 3.3 V | pass | 0 errors / 61 bits, CMD jitter 245.4 ps pp, post mism. 0 |
| corner096_typical_22_3.15 | 0.96 Gb/s | 2 | typical 22 C 3.15 V | pass | 0 errors / 61 bits, CMD jitter 260.6 ps pp, post mism. 0 |
| corner096_typical_22_3.35 | 0.96 Gb/s | 2 | typical 22 C 3.35 V | pass | 0 errors / 61 bits, CMD jitter 237.2 ps pp, post mism. 0 |
| corner096_typical_32_3.15 | 0.96 Gb/s | 2 | typical 32 C 3.15 V | pass | 0 errors / 61 bits, CMD jitter 264.5 ps pp, post mism. 0 |
| corner096_typical_32_3.35 | 0.96 Gb/s | 2 | typical 32 C 3.35 V | pass | 0 errors / 61 bits, CMD jitter 241.7 ps pp, post mism. 0 |
| corner096_ss_22_3.15 | 0.96 Gb/s | 2 | ss 22 C 3.15 V | pass | 0 errors / 60 bits, CMD jitter 347.0 ps pp, post mism. 0 |
| corner096_ss_22_3.35 | 0.96 Gb/s | 2 | ss 22 C 3.35 V | pass | 0 errors / 61 bits, CMD jitter 296.4 ps pp, post mism. 0 |
| corner096_ss_32_3.15 | 0.96 Gb/s | 2 | ss 32 C 3.15 V | pass | 0 errors / 60 bits, CMD jitter 363.7 ps pp, post mism. 0 |
| corner096_ss_32_3.35 | 0.96 Gb/s | 2 | ss 32 C 3.35 V | pass | 0 errors / 61 bits, CMD jitter 307.6 ps pp, post mism. 0 |
| corner096_ff_22_3.15 | 0.96 Gb/s | 2 | ff 22 C 3.15 V | pass | 0 errors / 60 bits, CMD jitter 220.1 ps pp, post mism. 0 |
| corner096_ff_22_3.35 | 0.96 Gb/s | 2 | ff 22 C 3.35 V | pass | 0 errors / 61 bits, CMD jitter 202.9 ps pp, post mism. 0 |
| corner096_ff_32_3.15 | 0.96 Gb/s | 2 | ff 32 C 3.15 V | pass | 0 errors / 61 bits, CMD jitter 224.1 ps pp, post mism. 0 |
| corner096_ff_32_3.35 | 0.96 Gb/s | 2 | ff 32 C 3.35 V | pass | 0 errors / 60 bits, CMD jitter 206.8 ps pp, post mism. 0 |
<!-- RESULTS:END -->

## Known limitations and open items

1. **Current netlist unsimulated** (see Evidence currency).
2. **Quarter rate (1.92–2.97 Gb/s) does not close** with the generic layout;
   half rate closes at 0.96 Gb/s on all corners and 1.25 Gb/s except ss;
   full rate only at 0.48 Gb/s.  Fix: port the 4:1 window mux, retime flops
   and window drivers to compact fast cells.  The unconverged attempt is
   `cells_fastpath_wip.py` + `wtx_fast.py` (cells `generated/fast/wtx_win`,
   `wtx_mux4`, `wtx_cinv8`, each DRC 0 / LVS unique; timing's `ct_tspcd`
   and `ct_mux4` are copied in by `wtx_fast.py`): its best variant reached
   2.5 Gb/s quarter rate with 0 errors extracted, 2.97 Gb/s never closed.
   The limit is retiming latency (window → TSPC → output ≈ 0.7 ns against
   0.8 ns at 2.5 Gb/s) and the register-clock delay spread (0.4–1.2 ns).
3. `pt_wordclk` (timing) is to replace the internal ÷5 (`wtx_div5`); half
   and full rate then need a stride mux at the shift registers.
4. `wtx_ext_rx` fails from the first bit at 0.5 Gb/s (baseline wander) and
   at 2 Gb/s.
5. USB HS through `pt_wiredtx` full-rate data into 45 Ω per leg is not
   simulated; `pt_wtx_hsbias` LSB reaches 3.5 mV at ss (target 2.4 mV).
6. `MODE_H`/`MODE_F`, the HS bias code/enable and `SER_EN` composition need
   register fields / glue.
7. Integration runs use an ideal termination common mode; the pads
   termination buffer, package and board are not included.  Ring phase
   error, jitter and duty-cycle error are not modelled (ideal phases).
