# Wired-TX family (`analog/wired_tx`)

Serializer, pre-driver gating and tail-bias DACs (`pt_wiredtx`), the `tmds`
configuration, the `wtx_ext_rx` receiver instance and the USB HS bias DAC
(`pt_wtx_hsbias`).  Ring phases come from timing's shared `pt_pll_ring`.
Nothing here is qualified; numbers are extracted (Magic C) unless noted, and
`generated/*-evidence.json` is the record of truth.

| Block | Layout | DRC (Magic / KLayout) | LVS | Extracted function | Four-test (safe / clean / observable / fallback) |
| --- | --- | --- | --- | --- | --- |
| `wiredtx` (`pt_wiredtx`) | 546.9 × 609.9 µm = 0.334 mm² (cap 0.30 incl. attached_tx_buffer: **over**, WT18), 1067 devices incl. core macro `wtx_serq4c` 532 × 298 µm | 0 / 0 | unique | core macro: 60/60 envelope runs 0 errors (2.5 Gb/s q, 1.62 h = 3.24 core rep2, 0.48 f = 1.92 core rep4); block: 1.25 Gb/s h tt 0/221 errors, eye 744 ps; block envelope in progress | pass / pass / pass / pass (risk: INT-02) |
| `tmds` | configuration of `wiredtx` + pad TMDS branch | (wiredtx) | (wiredtx) | 1.25 Gb/s into 50 Ω pull-ups: eye 955 mV / 663 ps, 1.16 Vpp diff | pass / pass / pass / pass |
| `wtx_ext_rx` | instance of timing's `pt_diff_clk_rx` (`wtx_ext_rx.spice`) | timing | timing | ideal DX: 1 Gb/s, 0 errors, eye 388 mV / 965 ps at the pad; through the extracted receiver: 5/43 errors at 0.5 Gb/s (start-up), no output at 2 Gb/s | pass / pass / pass / n/a |
| `usb_hs_bias` (`pt_wtx_hsbias`) | 125.8 × 76.0 µm = 9,552 µm², 53 devices | 0 / 0 | unique | 0–0.58 V full scale (tt), monotonic at all corners, settles to 1 LSB in 0.47 µs | pass / pass / open / n/a |

**Status 2026-11-11 (session 7, path A = CMOS quarter-rate core + WT12 repetition).**

* **Core macro `wtx_serq4c` extracted, 20 in-window corners × {2.5 Gb/s quarter, 3.24 Gb/s core rep2
  (1.62 Gb/s line), 1.92 Gb/s core rep4 (0.48 Gb/s line)}: 60/60 pass, 0 errors.**  Worst eyes: 2.5 Gb/s
  227 ps of 400 (ss/32/3.15); 3.24 rep2 427 ps of 617 (ss/32/3.15); 1.92 rep4 2065 ps of 2083.
  (scratch/wired_tx/s7/env, netlist sha256 87b28e23.)
* Two real core bugs fixed (both were failing the session-6 envelope):
  1. merged-NAND TSPC (timing's `_tspc_nand_cols`) charge-shared its clock-PMOS node onto X during
     CK high: at ff and the 480 MHz ring the shift flops flipped half a period early (43/140 errors).
     `serq4_macro._tspc_nand_cols` is now charge-sharing safe (a clock PMOS next to X per input).
  2. stream load flag: NOR -> INV4 -> INV4 left the loaded bit < 0.3 T to settle at ss/32/3.15 and
     the 3.24 Gb/s core rate; the LD flop now has an INV output that drives LD directly.
* Block benches: the /5 word counter has no reset, so `WORD_CLK40`'s phase differed between the
  phase pass and the data pass (by one register period); data was launched on the wrong side of the
  load and every extracted block run failed.  The benches now re-align on the measured `WORD_CLK40`
  edge and launch the 40-bit word 1.0 ns after it (the digital's clock-to-Q; interface WT16). (risk: WTX-02)
* Layout published: Magic DRC 0, LVS unique, KLayout 0.  pt_wiredtx has no poly resistors.
* Open: block-level envelope (priority corners running), postcursor in rep modes (DP is one *core*
  UI, i.e. ½ / ¼ user UI late in half / full rate), area (WT18), X5, CML stretch (does not fit the cap). (risk: WTX-06)

**Status 2026-11-10 (this pass).**  The serializer was rebuilt around a
compact TSPC core (`wtx_serq4`) that serves quarter, half and full rate; the
old generic serializer remains as the rate-code-11 fallback.

* **Schematic:** 0 errors at 3.24 Gb/s quarter rate (ring 810 MHz, the top of
  the plan) at tt/ss/ff/sf/fs, 1.62 Gb/s half and 0.81 Gb/s full rate at
  ss/22 °C/3.15 V; generic fallback 1.25 Gb/s tt.  Core windows 307–316 ps
  against a 309 ps UI at ss/tt/ff.
* **Layout:** 2081 devices, Magic DRC 0, KLayout 0, LVS unique,
  **0.337 mm² (allocation 0.30, over; interface WT3)**.
* **Extracted: fails.**  2.5 Gb/s quarter rate at tt/22/3.15: 37/141 errors,
  310 ps pp jitter.  The generic row placer scatters the core, so routing
  skews the core phases (extracted rise spacing 373–432 ps at tt and
  114–748 ps at ss against a 400 ps UI), and adjacent windows overlap.  **Next
  step: hand-place `wtx_serq4` as one compact macro with matched phase
  routing** (as done for the slicer's `ws_sa`), then rerun
  `./run_wired_tx.sh sims` (the job list already holds the 20-point envelope
  sets: quarter 2.5 and 3.24, half 1.62, full 0.81).
* **The ss/22 °C/3.15 V abort (previous record) is a bench problem, not the
  DUT.**  It reproduces deterministically with ngspice 43 and the pads' patched
  ngspice 47, always at the end of a PULSE/PWL source corner, on a source branch
  current (`vttmds#branch`, later `vtpost`, `vd19`, `vtmdsc7`).  The DUT has no
  floating node (a topology scan of the extracted netlist found none).  With
  abstol relaxed (diagnosis only) the same deck runs, so only current
  unknowns fail to converge.  At the tiny step forced after a corner they are
  dominated by C/h terms of pF gate/wire capacitance.  Fix: breakpoint-free
  tanh-edge stimuli and realistic driver resistance (150 Ω phases, 1 kΩ
  logic); no tolerance changed.  The originally aborting case (old extracted
  netlist, ss/22/3.15, 0.96 Gb/s) then passes, 0/61 errors.  An earlier
  partial fix (dropping the ideal-source tail measurement) is kept: tail
  currents are measured by the DC benches.

## Reproduce

```
./run_wired_tx.sh                 # all stages
./run_wired_tx.sh layout          # netlist (cells.py) + layout + DRC/LVS + GDS/KLayout
./run_wired_tx.sh sims [job...]   # extracted simulations (all, or named jobs); WTX_JOBS=n parallel (default 3)
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
| `wtx_fast.py` | Builds `wtx_mux4`/`wtx_cinv8` and imports timing's `ct_tspcd`/`ct_div5`/`ct_mux4` into `generated/fast` |
| `cells_fastpath_wip.py` | Earlier unconverged fast-path attempt (superseded by `wtx_serq4` in `cells.py`; not used) |
| `generated/mag/`, `generated/mag_hsbias/` | Magic hierarchy (top + primitive cells) for `pt_wiredtx` and `pt_wtx_hsbias` |

## Architecture

```
 ring phases WTX_PH0/90/180/270 --+--> phase select (quarter: ring phases; half: ring/2 from 4 TSPC
                                  |    flops; full: ring/4 twisted ring) -> four core phases C0..C3, 1 UI apart
                                  |
 D0..D19 (D0 first) ----------> compact core wtx_serq4 (timing's ct_tspcd / ct_div5, wtx_mux4, wtx_cinv8):
                                   4 x 5-bit parallel-load TSPC shift registers, all on C2 (LD from ct_div5,
                                   same clock domain) -> per-stream retiming hops of +3 / +4 UI only
                                   -> F0..F3 -> 4:1 window muxes (window k = C(k) & C(k-1)):
                                   main Y/YB = F(k), postcursor DP/DPB = F(k-1)       WORD_CLK = bit/20
                                  |
 rate field 11 (fallback) ----> generic static-CMOS serializer (wtx_serq/wtx_phbuf, half rate)
                                  |
  DX (pt_diff_clk_rx on WTX_EXT_P/N) -> three-way one-hot select (core / generic / EXT, break-before-make
        for EXT) -> CMD_MAIN_P/N = data & EN_MAIN, CMD_TMDS_P/N = data & EN_TMDS, CMD_POST_P/N = post & EN_POST
                                                      |
                  pads: tx_steering_buffer (x6) -> tx_protected_pad selector gates / tails
  IBIAS (10 uA) -> mirror -> three 8-bit PMOS DACs -> MAIN_BIAS / POST_BIAS / TMDS_BIAS (pad tail gates)
```

* **Rate field (`MODE_H`, `MODE_F`):** 00 quarter (4 bits per ring cycle), 10
  half (2), 01 full (1) run the compact core; **11 runs the earlier generic
  serializer in half rate, kept as the fallback route**.  Ring 480–810 MHz
  covers 1.92–3.24 / 0.96–1.62 / 0.48–0.81 Gb/s.  Change only while stopped
  (`SER_EN = 0`).
* **Compact core timing.**  Every flop is a TSPC `ct_tspcd` on a gated core
  phase; there is no derived register clock.  The registers and the load
  signal share one phase (C2), so loading needs no crossing.  Each stream then
  reaches the phase that centres it on its mux window through hops of +3 UI
  or +4 UI only (stream 0: C2→C2→C2, 1: C2→C1→C0→C3, 2: C2→C1→C0→C0, 3:
  C2→C1→C1→C1), so every crossing has hop − tcq ≥ 1.7 UI at 3.24 Gb/s
  (tcq ≈ 0.4 ns ≈ 1.3 UI).  All streams reach the line three register
  periods after the load, in order.  The four core phases have separate,
  identically loaded drivers for the windows (two NAND inputs each), the
  hops, the register bank (two drivers of ten flops) and the divider; the
  window gates are skewed (NAND 8/8, inverter 8/20) so a window is 1 UI wide
  (schematic, 3.24 Gb/s: 307 ss / 314 tt / 316 ff ps against a 309 ps UI).
  LD/LDB are buffered: LD changes 1.2–2.1 UI after a register edge and
  1.9–2.8 UI before the next.
* **Half/full rate** use the same core with four phases derived from the
  ring: half = a (toggle on PH0), c = a@PH180, b = a@PH0, d = c@PH180;
  full = a 4-flop twisted ring on PH0.  Every derived phase is a flop output,
  so all four carry the same clock-to-Q.
* **Design history in this pass (each found by simulation, all fixed):** LD
  handed to another phase domain with 0.2 ns margin (stream errors at 3.24
  Gb/s); ct_div5 racing to ÷4 at ff on a slow shared clock edge; windows
  355–383 ps wide (AND-OR mux ORed neighbours at ss); LD from a minimum NOR
  2–2.8 UI late; uneven phase loads (PH0/PH180 carried extra gates, window 2
  narrowed to 241 ps); a net-name collision (`QRA`/`QRB`) shorting the reset
  chain.
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
| `WTX_PH0/90/180/270` | in | ring phases via the clockmux (stopped = PH0=PH90=0, PH180=PH270=1); equal gate load on all four, route length-matched (interface WT2) |
| `MODE_H`, `MODE_F` | in | rate field: 00 quarter, 10 half, 01 full (compact core), **11 = generic serializer, half rate (fallback)**; change only while stopped |
| `D0..D19` | in | 20-bit double word from `rtl/pt_pattern.sv`; D0 first on the line |
| `WORD_CLK` | out | bit rate / 20 (40 % duty) for the word source and `WCLK_OBS` (from the active serializer: core divider or generic divider) |
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
Latency word launch → line ≈ 23 bits (generic serializer).  The compact
core uses the same divider sequence (`ct_div5`, `WORD_CLK` = state C, load
three register periods after `WORD_CLK` rises), so the same SDC relation
holds; its setup/hold numbers about that edge have not been re-measured.

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
<!-- RESULTS:END -->

## Known limitations and open items

1. **Extracted compact core fails** (layout skew, see Status).  Hand-placed
   core macro is the open item; until then no extracted rate above the
   generic fallback is qualified. (risk: WTX-06)
2. **40-bit boundary (S3) not implemented** (interface WT5); PCIe swing needs
   `current_code` 200–240 (WT4, integration runs queued in the job list);
   TMDS 1.485 Gb/s (`int_tmds_h1g485`) and ff-clamp TMDS not yet run on the
   new netlist.  Pad C / T-coil and clamp leakage are pads items (WT7). (risk: WTX-02)
3. `pt_wordclk` (timing) is to replace the internal ÷5 (`wtx_div5`); half
   and full rate then need a stride mux at the shift registers. (risk: WTX-02)
4. `wtx_ext_rx` fails from the first bit at 0.5 Gb/s (baseline wander) and
   at 2 Gb/s. (risk: TIM-08)
5. USB HS through `pt_wiredtx` full-rate data into 45 Ω per leg is not
   simulated; `pt_wtx_hsbias` LSB reaches 3.5 mV at ss (target 2.4 mV). (risk: USB-02)
6. `MODE_H`/`MODE_F`, the HS bias code/enable and `SER_EN` composition need
   register fields / glue.
7. Integration runs use an ideal termination common mode; the pads
   termination buffer, package and board are not included.  Ring phase
   error, jitter and duty-cycle error are not modelled (ideal phases). (risk: WTX-06)
