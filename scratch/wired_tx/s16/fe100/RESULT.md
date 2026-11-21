# fe100: 100BASE-TX transmit amplitude of pt_wiredtx8 at the RJ45 (WR-100TX-TXLVL)

## Limits (declared 2026-11-21 before any run)
* Peak differential amplitude of the settled +1 and -1 levels at the RJ45 (100 ohm, after B39 and magnetics): **950-1050 mV**.
* Amplitude symmetry |V+1| / |V-1|: **0.98-1.02**.
* Negative control: with POST_POL = 0 and the same stream, the +-1 levels must NOT appear (MAIN and POST cancel).
* (added 2026-11-21 for the Options section, before the option runs) Return loss at the RJ45, line side, 100 ohm reference (WR-100TX-RL): **>= 16 dB 2-30 MHz, >= 16 - 20 log10(f/30 MHz) dB 30-60 MHz, >= 10 dB 60-80 MHz**.
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

## Options (request from the coordinator via wired-TX owner, 2026-11-21)
**Bench:** `opts.py` (wraps `sweep.py`, the bias-path bench). It reads +3.4 % against the full chain at the base point. The "cal." column is the ss-pess value x 0.967; the factor was checked only at the base point.
* The RL limit (WR-100TX-RL, declared above) is checked at the RJ45, line side, 100 ohm reference, 2-80 MHz, at tt. Two pad states:
  * "held": the -1 state at code 255/255, the worst case because the conducting leg may leave saturation;
  * "off": tails off (code 0), the network alone.
* Gate levels are scaled from the ss full chain (0.330 / 0.848 x VDD; an assumption at tt/ff, see the State section). Code 255/255 unless stated.
* **Run log:**
  * The first transient pass failed on a wrong probe name (`xpad.esd_rail`) and was rerun.
  * The ss-pess W rows of that rerun were void: the pess pass renames the pad gate nodes before scaling. Fixed (the pad is now scaled before pess) and rerun.
  * Rows below are final.

### Cascode device and limits read from the pad netlist (tx_rt)
* **Cascode:** 16 x `nfet_06v0` (W 16 um, L 0.7 um) per leg, gate `CASCODE`, drain `PAD_x`, source `SUM_x_D_k`. Rated 6.0 V (GF180 6 V device).
* **Switches:** `nfet_03v3` (W 20 um, L 0.28 um), rated 3.3 V (max 3.63 V). Their drains sit on `SUM_x_D_k`, so **SUM max must stay <= 3.63 V**.
* **ESD:** PAD to `diode_pd2nw_06v0` to an **isolated ESD_RAIL**, with an RC-triggered `nfet_06v0` clamp to VSS (304 fingers). There is **no diode to VDD**, so a pad above VDD only charges ESD_RAIL to about PAD - 0.9 V.
  * CT 4.0 / 4.5 / 5.0 V: ESD_RAIL 3.0 / 3.5 / 4.0 V. CT current minus the leg currents: **|leakage| < 1 uA** at every corner. The clamp stays off.
  * **CT ceiling** = 6 V device rating, not ESD. At CT 5.0 V the cascode drain sees 4.87 V (19 % margin to 6.0 V). Recommended CT <= 4.5 V (drain 4.33 V, 28 % margin; it leaves room for overshoot at line connect/ESD events).
  * Not checked here: the other devices on PAD (termination switches, detect). Pads must confirm they are 6 V devices.

### Ranked table (ss-pess decides; "max" = maximum over the 4 corners)
| rank | option | ss-pess mV (cal.) | ss | tt | ff | symmetry worst | held leg mA (ss-pess / ff) | pad pin min V | SUM min / max V | cascode max Vgs / Vgd / Vds / Vd V | RL tt held / off, worst margin | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **pad switch + cascode W x2, B39 CT 4.5 V** | 1031 (**997**) | 1039 | 1210 | 1232 | 0.996 | 41.9 / 50.7 | 2.14 | 0.61 / 2.45 | 2.64 / 2.21 / 2.64 / 4.33 | not run with CT 4.5 V; W x2 alone +0.3 dB held / -0.8 off (79 MHz), CT 4.5 alone -0.8 / -0.9 | **meets 950 with 47 mV (cal.) margin at ss-pess.** tt/ff over 1050 at 255; by code: **ff 215 gives 1048 mV** (200 gives 978), **tt 215 gives 1046 mV**, symmetry 1.000. Per-board code calibration (B11). Needs a 4.5 V board rail and pad re-layout. Pad C 1.48 -> **1.71 pF per pin (+0.22 pF)**, measured at 50 MHz |
| 2 | W x2 + CASCODE 4.5 V + CT 4.5 V | 1217 (1177) | 1225 | 1232 | 1245 | 0.997 | 49.3 / 51.0 | 2.17 | 0.88 / 3.35 | 3.62 / 3.23 / 1.73 / 4.31 | -0.6 / -0.9 (79 MHz) | meets at ss-pess with large margin. Needs a 4.5 V cascode source as well. SUM max 3.35 V is close to the 3.63 V switch limit. 51 mA in one leg = the IX-9 limit |
| 3 | CASCODE 5.0 V + CT 4.5 V | 1101 (1065) | 1101 | 1187 | 1224 | 0.984 | 44.3 / 49.9 | 2.19 | 0.86 / **3.68** | 4.15 / 3.63 / 1.66 / 4.33 | -0.6 / -0.9 | amplitude OK, but **SUM max 3.68 V at ff exceeds the 3.63 V switch rating**: reject unless CASCODE is 4.5 V |
| 4 | W x2 + CASCODE 4.5 V | 1027 (994) | 1027 | 1045 | 976 | **0.930** | 41.3 / 42.6 | **1.37** | 0.53 / 2.91 | 3.97 / 3.76 / 1.48 / 3.11 | not run | amplitude meets at ss-pess, but **symmetry fails (0.93-0.97) and the pad pin is at 1.37 V** |
| 5 | W x2 (CT 3.3, CASCODE = VDD) | 943 (912) | 943 | 1000 | 949 | 0.934 | 38.0 / 41.6 | 1.40 | 0.48 / 2.16 | 2.92 / 2.67 / 1.73 / 3.14 | +0.3 / -0.8 | short by 38 mV (cal.); symmetry fails at tt/ff |
| 6 | CASCODE 5.0 V | 898 (868) | 898 | 921 | 871 | 0.943 | 36.1 / 38.8 | 1.49 | 0.58 / 3.09 | 4.45 / 4.10 / 1.73 / 3.16 | +0.5 / -0.4 | short |
| 7 | CASCODE 4.5 V / 4.0 V | 874 / 833 | 873 / 832 | 901 / 871 | 853 / 828 | 0.945 / 0.949 | 35.1 / 33.5 | 1.51 / 1.53 | 0.57 / 2.83 (4.5) | 3.96 / 3.58 / 0.81 / 3.14 (4.5) | +0.4 / -0.9 (4.5) | short |
| 8 | W x1.5 | 842 (814) | 841 | 927 | 893 | 0.941 | 34.0 / 39.7 | 1.46 | 0.47 / 2.11 | 2.92 / 2.58 / 1.57 / 3.15 | -0.05 / -0.8 | short |
| 9 | magnetics 1:n, n = 0.75 / 0.70 / 0.65 | 781 / 790 / 779 | 780 / 787 / 771 | 776 / 737 / 683 | 644 / 573 / **486** | 0.994-1.040 | 24.4 / 23.2 / 21.6 | **1.15 / 1.05 / 0.94** | 0.31-0.41 / 1.70 | 3.14 / 2.89 / 1.47 / 2.83 | **held -4.1 / -6.3 / -8.2 dB (at 2 MHz)**; off +1.1 / +1.9 / +3.0 | **reject.** The leg drop grows as 37.4 I / n^2, the tails collapse (ff worst) and the held-state RL fails |
| 10 | rail gates (0..VDD) | 670 (648) | 669 | 830 | 927 | 0.971 | 27.1 / 38.6 | 1.49 | - | - | - | short |
| 11 | B39 CT 5.0 / 4.5 / 4.0 V alone | 662 / 656 / 650 | 661 / 656 / 650 | 847 / 837 / 824 | 1028 / 992 / 954 | 0.978 | 27.2 / 43.4 | 2.60-3.57 | 0.44 / 1.69 | 2.74 / 1.72 / 3.39 / **4.87** (5.0) | -0.8 / -0.9 | no help at ss. The SUM node (cascode at VDD) limits there, not the pin |

**Magnetics network derivation** (option 9, chip:line = 1:n, n < 1):
* The line load reflects to the chip side as 100 / n^2.
* Back-termination R_b = 49.9 / n^2 per leg to the CT. The line then sees n^2 x 2 R_b = 100 ohm.
* Filter impedance-scaled: L = 98 nH / n^2 per leg, C = 19.6 pF x n^2 differential. OCL referred to the chip side: 350 uH / n^2.
* Result: V_line = 25 I / n, leg drop = 37.4 I / n^2. At n = 0.70: R_b = 101.8 ohm, L = 200 nH, C = 9.6 pF.
* Model: ideal transformer as an E/F pair.

**RL notes:**
* The base B39 network fails WR-100TX-RL by 0.5-0.9 dB at **79-80 MHz** (9.1-9.5 dB against 10 dB) in every non-1:n variant, including tails off. This is the 115 MHz Butterworth roll-off, a **board item for B39** (raise fc, use Bessel values, or retune C), independent of the on-chip options.
* 2-60 MHz passes with >= 8 dB margin, except for the 1:n options.

**Recommendation:** option 1 (pad switch + cascode W x2, B39 CT 4.5 V).
* Pads: re-layout of the txpad switch and cascode slices at 2x W (+0.22 pF per pin).
* Board: 4.5 V TX centre-tap rail in place of 3.3 V.
* Digital and board: per-board code calibration, about 215 at tt/ff and 255 at ss.

It needs:
* confirmation by pads that every device on PAD tolerates 4.5 V;
* a full-chain run on the re-laid-out pad;
* a WT52 / PC-63 update: held leg about 42 mA at ss-pess and up to 51 mA at ff at 255, about 43 mA at code 215.

**100BASE-TX is therefore not impossible, but it does not close without a pad change.** Board-only options (CT alone, 1:n magnetics) do not reach 950 mV at ss.

Result files: `results/O_*.json`, runs `jobs2.sh` / `jobs3.sh` / `jobs4.sh` (`*.out`), bench `opts.py`.

### Option 1b: CASCODE raised only in 100BASE-TX mode (W unchanged, no added pad C) + B39 CT 4.5 V
* Requirement: **SUM max <= 3.3 V** (switch rating). SUM max sits on the OFF leg, about CASCODE - Vt at low current, so it **rises when the code is lowered**.
* "cal." = raw x 0.967 (ss-pess only).
* Runs: `jobs5.sh` plus the single runs `O_cas4.2_ct4.5_ff_{212,220,230}`.

| CASCODE V | corner | code | amp raw mV (cal.) | sym | held leg mA | pad pin min V | SUM min / max V | cascode max Vgs / Vgd / Vds V | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 4.5 | ss-pess | 255 | 1046 (**1012**) | 0.994 | 42.1 | 2.42 | 0.82 / 3.02 | 3.68 / 2.77 / 1.98 | pass, 62 mV margin (cal.) |
| 4.5 | ss | 255 | 1046 | 0.994 | 42.1 | 2.40 | 0.82 / 3.01 | 3.69 / 2.78 / 1.99 | pass |
| 4.5 | tt | 255 | 1153 | 0.984 | 46.6 | 2.29 | 0.82 / 3.11 | 3.68 / 2.97 / 1.75 | over 1050: lower the code |
| 4.5 | tt | 230 | 1104 | 0.995 | 44.4 | 2.39 | 0.89 / 3.18 | 3.61 / 2.89 / 1.80 | over 1050 |
| 4.5 | tt | **215** | **1044** | 0.999 | 42.1 | 2.46 | 0.97 / **3.21** | 3.53 / 2.80 / 1.82 | **pass** |
| 4.5 | ff | 255 | 1210 | 0.982 | 49.2 | 2.21 | 0.83 / 3.20 | 3.67 / 3.09 / 1.56 | over 1050 |
| 4.5 | ff | 230 | 1113 | 0.998 | 45.7 | 2.35 | 0.94 / **3.31** | 3.56 / 2.97 / 1.61 | SUM > 3.3 V |
| 4.5 | ff | 215 | 1045 | 0.999 | 42.9 | 2.44 | 1.07 / **3.33** | 3.43 / 2.83 / 1.63 | **SUM > 3.3 V: 4.5 V not allowed at ff** |
| 4.2 | tt | 255 | 1112 | 0.988 | 45.3 | 2.33 | 0.78 / 2.80 | 3.42 / 2.62 / 1.92 | - |
| 4.0 | tt | 255 | 1082 | 0.992 | 43.8 | 2.34 | 0.75 / 2.59 | 3.25 / 2.37 / 2.03 | - |
| 4.2 | ff | 255 | 1190 | 0.979 | 48.5 | 2.23 | 0.80 / 2.90 | 3.40 / 2.75 / 1.74 | over 1050 |
| 4.2 | ff | 230 | 1126 | 0.997 | 45.5 | 2.36 | 0.89 / 3.04 | 3.31 / 2.65 / 1.81 | over 1050 |
| 4.2 | ff | 220 | 1083 | 0.999 | 43.8 | 2.41 | 0.96 / 3.06 | 3.24 / 2.57 / 1.83 | over 1050 |
| 4.2 | ff | **212** | **1046** | 0.999 | 42.3 | 2.47 | 1.02 / **3.07** | 3.18 / 2.50 / 1.84 | **pass, SUM 0.23 V under the limit** |
| 4.0 | ff | 255 | 1164 | 0.979 | 47.7 | 2.25 | 0.78 / 2.68 | 3.22 / 2.52 / 1.85 | - |
| 5.0 | ss-pess / ss / tt / ff | 255 | 1101 (1065) / 1101 / 1187 / 1224 | >= 0.984 | 44-50 | >= 2.19 | - / **3.47-3.68** | 4.15 / 3.63 / 1.66 | **reject: SUM > 3.3 V at every corner** |

* **Result:** CASCODE about 4.5 V at ss and tt and 4.2 V at ff closes the gap without added pad C. This is roughly a corner-tracking level: about VDD + 1.35 V at ss, VDD + 1.2 V at tt, VDD + 0.75 V at ff. Better still, a replica that holds CASCODE = 3.3 V + Vt(6 V nfet at about 0.5 mA) + about 0.2 V, which tracks the off-leg SUM level directly.
  * ss-pess, code 255: **1012 mV cal.**, symmetry 0.994, SUM max 3.02 V.
  * tt, code 215: 1044 mV, SUM max 3.21 V.
  * ff, code 212: 1046 mV, SUM max 3.07 V.
  * All cascode voltages are <= 3.7 V Vgs, 3.1 V Vgd and 2.0 V Vds, well inside the 6 V rating. The cascode drain reaches 4.33 V (it sits at the CT).
* **Constraints:**
  * The SUM limit binds at the **lowest code used**: re-check SUM after any per-board code calibration.
  * The held leg is 42-43 mA at the calibrated codes and 49 mA at ff code 255. WT52 / PC-63 need a re-basis.
* **Versus option 1 (W x2):** about 15 mV less margin at ss-pess, no pad C, but it needs the mode-switched cascode bias source (charge pump / regulator above VDD) plus the 4.5 V CT rail. RL is unchanged from the base network (the same 79-80 MHz board-filter miss).
