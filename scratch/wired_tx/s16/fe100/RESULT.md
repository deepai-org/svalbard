# fe100: 100BASE-TX transmit amplitude of pt_wiredtx8 at the RJ45 (WR-100TX-TXLVL)

## Limits (declared 2026-11-21 before any run)
* Peak differential amplitude of the settled +1 and -1 levels at the RJ45 (100 ohm, after B39 and magnetics): **950-1050 mV**.
* Amplitude symmetry |V+1| / |V-1|: **0.98-1.02**.
* Negative control: with POST_POL = 0 and the same stream, the +-1 levels must NOT appear (MAIN and POST cancel).
* Pad leg compliance at the highest current: PAD_P/N >= 1.7 V (IX-9), and leg current that tracks the code (no tail collapse).

## State (2026-11-21): FAIL. Full scale does not reach 950 mV at any corner
**No code reaches 950 mV at ss-pess, ss, tt or ff.** Full scale (MAIN 255 + POST 255, the DAC maximum; the codes are 8-bit) gives:
* **614 mV at ss-pess** (full chain, extracted)
* 635 mV at ss and 771 mV at tt (bias-path bench)
* 783 mV at ff (bias-path bench). At ff the amplitude *falls* as the code rises: 814 mV at code 200 is the ff maximum in the sweep.

Because the maximum is below 1050 mV at every corner, no code is needed to stay under 1050 mV at ff.

**Cause: the pad's internal headroom, not the board.** MAIN + POST in one leg should give 2 x 18.8 = 37.6 mA at ss, but the held level carries only 26.3 mA. The pad pin stays at >= 1.9 V. The internal summing node SUM_x_D (the drain of the switches, below the 6 V cascode whose gate is at CASCODE = VDD) falls to about 0.7 V on the conducting side. The 3.3 V switch and the tail then leave saturation.

The current therefore saturates (ss 26.3 mA, tt 33 mA, ff 36.4 mA) almost independently of the code:
* At ss, codes 200 to 255 change the amplitude by only 621 to 635 mV.
* At ff, the off leg also conducts 4 mA, because the mux gate low level is about 1.1 V. That lowers the amplitude and the symmetry.

Lowering the B39 centre tap to 3.234 V (-2 %) costs only 2 mV, which confirms the limit is on chip.

What would fix it (owners' decision, not done here):
* a higher CASCODE gate voltage,
* larger cascode and switch devices,
* full-swing gates (the "rail" rows below: +35 mV at ss, +144 mV at ff, still short of 950 mV),
* or splitting MAIN and POST so that each sums through its own cascode slices.

At the network's 25 ohm, 950 mV needs 38 mA of differential current in one leg, held.

## Bench
* **Full chain (anchor):** `anchor.py`.
  * Netlist `net/pt_wiredtx8.fullfix16.rc.spice` (s16 snapshot, Magic extresist + fixcap16, sha256 08338a4c...; before the pending NAND phase-buffer change).
  * **Real ring:** extracted pt_pll_ring_core (layout-11Nov), pess. at ss-pess, open loop at the s12 tune, 312.43 MHz, route 30 ohm / 75 fF. That gives a 2.4995 Gb/s core, **n = 20** core bits per symbol, 125 MBd.
  * Pad RT (`txr/models/tx_rt.spice`) with TERM_ENABLE = 0.
* **Board (both benches, `net100.py`):**
  * COB bond 0.23 ohm + 2.82 nH (pess.), then the s13 COB package chain and a 50 mm 50-ohm carrier.
  * B39: 49.9 ohm to a 3.3 V CT per leg, 2 x 98 nH, 19.6 pF differential.
  * Magnetics 1:1 with 350 uH OCL, and 100 ohm at the RJ45.
* **Stream (`stream.py`):** scrambled idle (x^11+x^9+1) to MLT-3. Over 16376 symbols the levels are +1/0/-1 = 0.25/0.50/0.25, and the **longest held level is 12 symbols (96 ns)** for +1, -1 and 0 alike.
  * The sweep window (symbols 1100-1125, scored from symbol 6) contains that 12-symbol +1 hold.
  * The anchor ran 14 symbols to keep the run time down (2.3 h each).
* **Sweep:** `sweep.py`, the bias-path bench.
  * Schematic wtx8_aux + 2 x wtx_idac2m from `net/pt_wiredtx8.spice` with a 10 uA IBIAS, and the same pad and board.
  * Ideal 2.5 Gb/s gate sources at the block's measured output levels. The anchor measured **1.04-2.67 V at ss 3.15 V**. Other corners are scaled 0.330 / 0.848 x VDD (**assumption**). The `rail` rows use 0..VDD as an upper bound.
  * POST = MAIN delayed by one core bit.
  * Calibration: at ss-pess 255 the bias-path bench reads **635 mV against 614 mV from the full chain (+3.4 %)**.
* Corners: tt 27 C 3.30 V, ss 32 C 3.15 V, ss-pess (pess. parasitics as in chain16) 3.15 V, ff 22 C 3.45 V.
* Waveforms were deleted after parsing. One simulation ran at a time, with OMP_NUM_THREADS = 1.

## Table: corner x code (MAIN = POST, POST_POL 1, pad RT). Amplitude = min(|V+1|, |V-1|) settled at the RJ45

* Symmetry = V+1 / |V-1|, sampled at the 2nd symbol of each hold.
* Leg on / off = held-level current in the conducting / non-conducting leg.
* Peak = maximum leg current in the window.
* Window average = average over the 20 scored symbols (the P and N legs differ because the window holds the 12-symbol +1 run).

| corner | code | amp mV | sym | leg on mA | leg off mA | peak mA | window avg P / N mA | pad min V |
|---|---|---|---|---|---|---|---|---|
| ss-pess **full chain** | 255 | **614** | 1.000 | ~25 | - | 26.7 | 12.8 / 17.1 | 1.99 |
| ss-pess | 200 | 621 | 0.999 | 25.4 | 0.4 | 25.6 | 7.3 / 19.7 | 2.00 |
| ss-pess | 215 | 626 | 0.999 | 25.7 | 0.5 | 25.9 | 7.4 / 20.0 | 1.98 |
| ss-pess | 230 | 630 | 0.999 | 26.0 | 0.6 | 26.2 | 7.6 / 20.2 | 1.96 |
| ss-pess | 245 | 633 | 0.999 | 26.2 | 0.6 | 26.4 | 7.8 / 20.4 | 1.95 |
| ss-pess | 255 | 635 | 0.999 | 26.3 | 0.7 | 26.5 | 7.8 / 20.6 | 1.94 |
| ss | 200 | 620 | 0.999 | 25.4 | 0.4 | 25.6 | 7.3 / 19.7 | 1.98 |
| ss | 230 | 630 | 0.999 | 26.0 | 0.6 | 26.1 | 7.6 / 20.3 | 1.93 |
| ss | 255 | 635 | 0.999 | 26.3 | 0.7 | 26.5 | 7.9 / 20.6 | 1.90 |
| tt | 200 | 759 | 0.987 | 31.7 | 0.8 | 32.2 | 8.0 / 25.3 | 1.76 |
| tt | 230 | 770 | 0.986 | 32.5 | 1.3 | 33.1 | 9.9 / 25.1 | 1.71 |
| tt | 255 | 771 | 0.986 | 33.0 | 1.7 | 33.6 | 10.5 / 25.6 | **1.68** |
| ff | 200 | **814** | **0.963** | 35.2 | 1.8 | 36.3 | 9.6 / 27.8 | **1.67** |
| ff | 230 | 797 | 0.957 | 36.0 | 3.2 | 37.3 | 11.2 / 28.8 | 1.61 |
| ff | 255 | 783 | 0.960 | 36.4 | 4.2 | 37.8 | 12.3 / 29.5 | **1.58** |

ss codes 215 and 245: 626 and 634 mV (`RESULT.json`).

**Bounds and variants at code 255:**

| variant | result |
|---|---|
| rail gates, ss-pess | 670 mV |
| rail gates, ss | 669 mV |
| rail gates, tt | 830 mV |
| rail gates, ff | 927 mV, symmetry 0.971, pad 1.49 V |
| pad C, ss-pess | 646 mV |
| CT 3.234 V, ss-pess | 633 mV, pad 1.88 V |
| MAIN alone (POST off), ss-pess | about 465 mV (18.7 mA). This row's automatic fit is invalid: with POST off the start state is not cancelled, which leaves DC in the 350 uH; the value is read from the level swing |

**Minimum MAIN + POST for >= 950 mV at ss-pess and ss: none exists.** The 950 mV point needs >= 38 mA held in one leg; the block delivers at most 26.3 mA (ss) to 36.4 mA (ff) in a held level.

**Symmetry:** ss and ss-pess pass (0.999-1.000). **tt fails at 0.986, ff fails at 0.957-0.963.** The asymmetry grows with the off-leg leakage from the 1.1 V gate low level.

**Compliance:** pad pins >= 1.9 V at ss, but **1.68 V at tt and 1.58 V at ff**, below the 1.7 V of IX-9. The binding limit is the internal SUM node at about 0.7 V (ss), not the pin.

**Droop (magnetics) over the longest hold (12 symbols, 96 ns):** about -8 mV at ss and -9 mV at tt/ff, about 1.2 %.

## Per-leg currents (answers the coordinator's question; corrects WT52)
* **Peak in one leg:** 26.5 mA (ss), 33.6 mA (tt), 37.8 mA (ff), carried for the longest held level of **96 ns** (12 symbols). The WT52 assumption of 20 mA (2I with I = 10 mA) is exceeded at every corner when the codes are 200-255.
* **Long scrambled-stream average per leg** = 0.25 x on + 0.25 x off + 0.5 x I(0 level):
  * At ss-pess the 0 level carries 18.7 / 19.6 mA per leg (MAIN alone in one leg, POST in the other). That gives **about 16 mA per leg**, above the 10.5 mA in WT52 / PC-63.
  * tt and ff are higher (I(0) was not measured there).
* The total MAIN_CODE + POST_CODE = 400-510 also breaks WT52 rule (b) (<= 255). 100BASE-TX at these codes needs a pads EM re-basis (PC-63) or an exception, and it still does not reach 950 mV.

## Negative control
**Full chain, ss-pess, 255/255, POST_POL = 0: PASS.** The +-1 positions read -0.5 / -0.7 mV (cancelled), against 614 mV with POL 1.

The bias-path `_pol0` rows are not a valid control. Their level fit locks onto the 2.5 GHz-filtered 0-level pattern and gives meaningless numbers (-574 mV, symmetry -1.13). They are kept in the JSON, marked.

## Files (scratch/wired_tx/s16/fe100)
`RESULT.md`, `RESULT.json`, `stream.py`, `net100.py`, `anchor.py`, `sweep.py`, `jobs.sh` (+ `jobs.out`, `A_ssp_255_pol1.out`), `results/*.json`, `runs/*/tb.sp` (+ logs).
