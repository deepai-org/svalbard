# Wired receive family (`analog/wired_rx`)

Wired receive chain, risk-accepted and **not qualified**.  All numbers are
from Magic-extracted netlists (parasitic C) in ngspice; the per-block
`generated/<block>-evidence.json` is the record of truth.

| Block | Function |
| --- | --- |
| `pt_termination` | Termination control and the TERM_VCM common-mode source (resistors are in the pad bank) |
| `pt_rxlevel` | Divider/bypass control with hardware break-before-make |
| `pt_ctle` | CTLE with the `wire_ctle_bypass` switch |
| `pt_rxselect` | Input selector (CTLE or direct) |
| `pt_slicer` | Eight PMOS-input StrongARM samplers on ring phases `CKP0..7`; also the USB 2.0 HS receiver |
| `pt_detect` | Signal/threshold detect, USB HS squelch/disconnect, USB FS/LS single-ended receivers |
| `pt_cdr` | Dual-loop CDR analog cell (hand-over control + weak bang-bang pump on the RX `pt_pll_ring` loop filter) |
| `pt_wmon_sel` | WMON source selector for the shared `bb_tap` buffer |
| `pt_wrx_cap` (`capture.py`) | Fast-cell 1:N capture front end (8 samples per ring cycle → 20-bit data/edge words) |
| `rtl/pt_wrx_cdr_loop.sv` | Word-domain CDR logic (FLL step, bang-bang phase loop, full-rate phase picker, raw mode) |

## Reproduce

```
./run_wired_rx.sh                          # all analog blocks + CDR RTL check + evidence
./run_wired_rx.sh --blocks ctle --no-corners
python3 capture.py                         # pt_wrx_cap fast cells -> generated/fast/
```

`run_wired_rx.sh` → `run_family.py`: schematic generation (`netlists.py`),
Magic layout/DRC/extraction and Netgen LVS (`svalbard/librelane-gf180-canary:2026.08`,
Magic 8.3.623, Netgen 1.5.316), GDS export with the analog image's Magic
8.3.678 plus KLayout GF180 DRC, extracted ngspice (`hpretl/iic-osic-tools@sha256:89641950…`)
at nominal (tt/27 °C/3.3 V) and the 12-point envelope (tt/ss/ff × 22/32 °C ×
3.15/3.35 V), max-rate sweeps (non-gating), safety cases, the extracted CDR
runs with timing's `generated/pll_ring.ext.spice`, the CDR RTL check
(iverilog + yosys) and evidence JSON.  Containers run `--network none`; raw
output goes to `scratch/wired_rx/`.  `capture.py` is not yet part of
`run_family.py`: `build_cell` builds the rows, `build_top` assembles
`generated/wrx_cap.*` and `run_bench` simulates it.

| File | Role |
| --- | --- |
| `netlists.py` | Schematic generator: `<block>.spice` (top `pt_<block>`, gf180mcuD devices only); rejects net names that differ only in case |
| `wrx_flow.py` | Layout generator (compact PCell rows, per-row Metal4 tracks, Metal5 trunks), DRC/extraction/LVS, GDS export, ngspice runner |
| `sims.py` | Testbenches, instantiating blocks by port name (same bench for schematic and extracted) |
| `run_family.py`, `evidence.py`, `run_wired_rx.sh` | Orchestration and evidence |
| `capture.py`, `wrx_compact.py` | `pt_wrx_cap` cells and top (compact rows from timing's `compact.py`/`fastcells.py` patterns, placed with timing's `layout_engine`) |
| `rtl/` | `pt_wrx_cdr_loop.sv` and its behavioural closed-loop testbench |

Layout style: single-finger PCells in rows, one Metal4 track per net per row,
Metal5 trunks for multi-row nets, static ports interleaved between switching
ports, StrongARM integrating nodes guarded, one sampler/comparator per row.

## Architecture

Quarter-rate wired clocking with selectable bits per ring cycle (4 quarter,
2 half, 1 full) and no phase interpolator.  The RX ring is a second instance
of timing's `pt_pll_ring` (480–810 MHz, PH0..PH7 at 45°), driving the slicer
`CKP0..7`.

* **Frequency loop:** with `freq_hold=0` the PLL's own PFD/pump locks the ring
  to the reference.  `pt_cdr` supplies its 10 µA bias (`IB_PLL` → `IBIAS`)
  and passes `REF_IN → REF_PLL`.
* **Hand-over:** at the first `FBCK_IN` falling edge after `freq_hold`,
  `pt_cdr` holds `REF_PLL` low and clamps `IB_PLL` together, so the PFD parks
  onto an unbiased pump.  (`pt_pll_ring` r6 has a `HOLD` input; `pt_cdr`
  does not use it yet and the benches tie it low.)
* **Phase loop (half/quarter):** a weak bang-bang pump on `VCTRL`
  (= `pt_pll_ring.ATB_VCTRL`), about ±50 nA (×2 with `bb_gain`), source-side
  switches; the PLL's 20 kΩ gives the proportional path and its capacitors
  integrate.  `pt_wrx_cdr_loop` makes one early/late decision per word.
* **FLL step (`cfg_fll_en`):** after the hand-over the RTL counts ring words
  over 5·2^k reference cycles and pulses `bb_up/bb_dn` for |error|·2^shift
  words per window until |error| ≤ `cfg_fll_tol`, then starts the phase loop.
  The bang-bang loop alone captures about ±2000 ppm.
* **Full rate (480–810 Mb/s, USB HS):** the ring stays locked to the
  reference; 8× oversampling with a blind phase picker (`psel`, ≤ 1 step per
  3 words, hysteresis `cfg_pick_hyst`).  The 3↔4 wrap is reported as a one-bit
  slip (`SLIPP`/`SLIPM` → `SLP`/`SLM`) that the FPGA absorbs.
* **Raw mode (`cfg_raw`):** words pass through without loop action
  (external-clock / FPGA fallback).

### `pt_wrx_cap` contract

The capture front end runs at ring rate in compact fast cells (standard
cells cannot capture at 480–810 MHz at ss).  The word clock comes from
timing's `pt_wordclk`.

| Signal | Dir | Meaning / timing |
| --- | --- | --- |
| `S0..S7` | in | pt_slicer D0,E0,D1,E1,D2,E2,D3,E3 (phase order) |
| `CKP0..CKP7` | in | ring phases (pt_pll_ring PH0..7); external-clock fallback: CKP0..3 = CK, CKP4..7 = !CK |
| `EN` | in | 0 = clocks low, every flop reset, outputs 0 |
| `LDE` | in | pt_wordclk LDE (one CK period, once per word); fixes the word boundary |
| `B2`, `B1` | in | bits per ring cycle: 00 quarter, 10 half, 01 full |
| `PSEL[2:0]` | in | full rate data phase from pt_wrx_cdr_loop; applied from the next word |
| `SLIPP`, `SLIPM` | in | full rate: one word, with the PSEL step 3→4 (+1) or 4→3 (−1) |
| `DW0..19`, `EW0..19` | out | data/edge double word, bit 0 = oldest; change once per word and are sampled on `WORD_CLK` rise |
| `SLP`, `SLM` | out | slip of the word on DW (`SLP`: first bit duplicates the previous word's last bit; `SLM`: one bit lost before it) |

Mode mapping: quarter DW = D0..D3, EW = E0..E3 per cycle; half DW = D0, D2,
EW = D1, D3; full DW = phase PSEL (previous cycle for PSEL 4..7), EW = half a
UI later.  Edge k lies between data k and k+1.

## Ports, controls and register-map mapping (proposed)

| Block port(s) | Register field (proposed) | Notes |
| --- | --- | --- |
| `term_en`, `term_mode[1:0]` | `termination.config.*` | 00 off, 01 shunt to TERM_VCM 1.2 V, 10 100 Ω differential, 11 shunt to VSS (USB HS).  No per-leg trim hardware. |
| `rxlevel_en`, `rxlevel_half` | `rxlevel.config.path` | 0 off, 1 bypass, 2 half; break-before-make ≥ 5.7 ns in hardware |
| `ctle_en`, `ctle_peak[1:0]` | `ctle.state.state`, `ctle.config.zero_trim[1:0]` | 2-bit degeneration code |
| `wire_ctle_bypass` | `debug.wire_bypass.ctle` | |
| `rxselect_en`, `rxselect_direct` | `rxselect.state.state`, `rxselect.select.branch` | |
| `slicer_en`, `trim_<s>_{p0,p1,n0,n1}` | `slicer.state.state`, `slicer.offset.*` | 4 bits per sampler phase |
| `det_*`, `det_clk` | `detect.config.*` | 2-bit threshold codes; `det_src_tx` has no field yet |
| `cdr_en`, `bb_gain` | `cdr.config.enable`, `cdr.config.loop_gain_code[0]` | `freq_hold`, `BB_UP`, `BB_DN` from the RTL |
| RTL `cfg_bits_per_cycle`, `cfg_acq_words`, `cfg_raw`, `cfg_bb_invert`, `cfg_pick_hyst`, `cfg_fll_*` | `cdr.config.*` (new fields needed) | |
| `wmon_en`, `wmon_sel[1:0]` | `debug.wmon_select.select` | |

Supplies: `VDD_WIRE_SW`, except `pt_cdr` on `VDD_PLL_SW`.  IBIAS (ctle,
detect, cdr) is 10 µA sunk through an NMOS series switch (no current when
off).  Static control decode is hand-built gates.

### Hookups

* **Pad** (`analog/pads` wired_receive) owns the termination resistors,
  divider/bypass switches and USB pulls; this family drives `TERM_ENABLE`,
  `DIFF_ENABLE`, `TERM_VCM`, `DIV_ENABLE`, `BYPASS_ENABLE`.  `RX_P/N` feed
  ctle, rxselect, detect and wmon_sel.
* **WCLK_IN:** timing's `pt_diff_clk_rx` → clockmux → RX ring PLL reference
  or slicer clocks (integration item).
* **WMON:** rf_rx `pt_bb_tap` (`in_p = WMON_IN`, `in_n = VSS`); an NMOS
  follower, so USB HS levels (0–0.4 V) do not pass.
* **WCLK_OBS:** timing `pt_clk_obs` IN0 = QCK, IN1 = CKP0, IN2 = WCLK_CK,
  IN3 = word_clk.  WDBG_OBS comes from the register-file RTL.
* **ATB:** `atb_ctle_pbias` → `ctle_bias` (24), `TERM_VCM` →
  `termination_vcm` (27), `atb_det_vref` → proposed 28, `atb_cdr_pbias`;
  `VCTRL` is timing's `pll_ring.ATB_VCTRL` tap.

### USB settings

* HS receive: termination 11, rxlevel bypass, `rxselect_direct=1`, slicer at
  480 Mb/s (CM 0.2 V); squelch `det_thr=2` (≈125 mV, window 100–150 mV);
  disconnect `det_thr=3` (536–546 mV extracted, window 525–625 mV).
* FS/LS: `det_se=2` (1.4 V), SE_P/SE_N sampled on `det_clk`; SE0 in RTL.

## Results

Every block: Magic DRC 0, KLayout GF180 DRC 0 on the analog-image GDS, LVS
unique, HRES 62/0 present on every `ppolyf_u_1k`.  Extracted tt/27 °C/3.3 V;
ranges cover the 12-point envelope.

| Block | Devices | Area µm² (ceiling) | Key results | safe / clean / observable / fallback |
| --- | --- | --- | --- | --- |
| termination | 82 | 21 395 (200k) | TERM_VCM 1.225 V (1.16–1.25); USB ground switch 1.98 Ω; 1.0 mA | pass / pass / open / pass |
| rxlevel | 70 | 13 174 (50k) | break-before-make 6.5/7.0 ns (≥ 5.5) | pass / pass / open / open |
| rxselect | 26 | 8 841 (80k) | BW 2.43 GHz (≥ 2.0), direct 3.0 GHz | pass / pass / open / open |
| wmon_sel | 47 | 9 835 | BW 0.85 / 0.67 GHz into 300 fF; off loading 40 / 38 fF | pass / pass / open / open |
| ctle | 77 | 21 437 (200k) | DC gain +0.7 / −0.9 dB (codes 0/1); peaking up to 7.3 dB; −1.0 dB at 1.25 GHz, −4.1 dB at 2.5 GHz (code 3); 4.8 mA; RX_P load 180 fF | pass / pass / open / pass |
| slicer | 264 | 140 311 (360k) | 0 errors at 1 Gb/s and 480 Mb/s at every corner; offset −10 mV (−11..−7), trim −47..+33 mV | pass / pass / open / open |
| detect | 258 | 96 819 (180k) | code 1 at 66 mV; squelch 125.5 mV; disconnect 536–546 mV; FS/LS line state OK; receiver-detect 103 µA | pass / pass / open / open |
| cdr (analog cell) | 113 | 40 094 (300k) | IB_PLL 9.37 µA in acquisition, 0 in hold/off; BB pump +49.9 / −51.6 nA (+99.5 / −103.6 with bb_gain); off current 0 | pass / **fail** / open / open |
| cdr RTL | yosys generic synth OK | — | behavioural, 18/22 cases pass (below) | — |

**Slicer maximum line rate, quarter mode** (open loop, 200 mVppd, 0 errors in
~34 bits; not a BER):

| Corner group | 1.5 Gb/s | 2.0 Gb/s | 2.5 Gb/s | 2.97 Gb/s |
| --- | --- | --- | --- | --- |
| tt 27 °C 3.3 V | pass | pass | pass | pass |
| tt 22/32 °C × 3.15/3.35 V | pass | pass | pass | 2–3 errors |
| ff (4 points) | pass | pass | pass | pass |
| ss 22 °C 3.15 V | pass | 2 errors | fail | fail |
| ss other 3 points | pass | pass | 2–10 errors | fail |

4/5 Gb/s at tt fail (non-gating).  Derived per-mode limits (ring = line rate
× 4 / bits per cycle): half rate 1.25 Gb/s fits every corner except
ss/22 °C/3.15 V; full rate is slicer-limited at ss to ~0.38–0.5 Gb/s, so
**480 Mb/s USB HS is marginal at ss**.

**CDR extracted runs** (tt; `pll_ring.ext` r5 + `cdr.ext` [+ `slicer.ext`],
analog-behavioural phase detector standing in for the RTL):

| Run | Result |
| --- | --- |
| `acq_625m` (gating) | Lock 624.59 MHz (−656 ppm), FB−REF 637 ps; hand-over +1430 ppm, then stable; BB UP 100 ns −86 ppm (wrong sign), DN −2080 ppm → **fail** |
| `track_quarter` (gating) | 354 errors / 3424 bits; PD drives DN 41 % vs UP 17 %, ring runs to 611 MHz → **fail** |
| `track_half` (gating) | 33 errors / 1744 bits; ring within +0.3 % → **fail** |
| `dual_quarter_2g5_no_fll` (non-gating) | 579 errors / 3888 bits; ring drifts to 602.5 MHz |
| `dual_half_1g25_no_fll` (non-gating) | 189 errors / 1942 bits |

**CDR behavioural check** (`rtl/tb_pt_wrx_cdr_loop.sv`: RTL + analog loop model,
K_VCO 0.64 GHz/V, R 20 kΩ, C1 9 pF, C2 1 pF, 50 nA pump): 0 errors for
quarter/half at 0/±300 ppm and −5000 ppm SSC, full rate at 0/±500 ppm,
±2000 ppm hand-over steps, and with the FLL at +3.5 % (quarter, half) and
−2 % +300 ppm (quarter) with ±1 nA leak.  Fail: +4000 ppm step without FLL
(quarter, half); half −2 % −300 ppm with FLL (residual at the capture edge);
quarter +3.5 % with FLL during SSC.

**`pt_wrx_cap`:** schematic benches (`scratch/wired_rx/cap_*`, not an
evidence file): with the current `capture.py`, half 625 MHz 0/100 bit errors
and full 480 MHz psel 5 0/60; with the previous revision, quarter 810 MHz
0/120 and full 480 MHz psel 3 52/120 (fail).  No layout or extracted result
of the current netlist.

**Evidence currency:** `cdr.spice` (regenerated, now 125 devices,
51,673 µm² in `generated/cdr-layout.json`), `generated/cdr.ext.spice`,
`cdr.gds`, `netlists.py`, `sims.py` and both `rtl/*.sv` changed after
`cdr-evidence.json` and `cdr-rtl-check.json`; `netlists.py`, `sims.py`,
`run_family.py` and `evidence.py` changed after every other evidence file
(the block netlists and layouts themselves match).  Rerun
`run_wired_rx.sh`.

## Known limitations and open items

1. **CDR is not demonstrated end to end extracted** (half/quarter): the
   hand-over step (≈ ±0.4 %) exceeds the bang-bang capture range; the FLL
   that removes it is verified only behaviourally (needs > 100 µs ring time);
   the extracted tracking runs fail.  Suspects: the PD stand-in timing and
   formula, ring port-phase skew, one-word decision latency.  Open: SSC
   acquisition after a hand-over, half-rate FLL margin, lock at corners,
   use of `pt_pll_ring.HOLD`.
2. **`pt_wrx_cap` needs layout and extraction** of the current netlist
   (`capture.py` cells, `build_top`), integration into `run_family.py`, and a
   rerun of quarter rate and full rate psel 3 on the current netlist.  The `WORD_CLK`-to-word-load offset
   is not yet simulated with `pt_wordclk`.
3. **Redesigned `pt_cdr` is unsimulated** (see Evidence currency).
4. Slicer ss limit 1.5–2.0 Gb/s quarter rate; USB HS marginal at ss.
5. CTLE loses ~4.1 dB at 2.5 GHz; 5 Gb/s is exploration only.
6. Not implemented: termination trim, 8-bit detect thresholds, test-current
   trim, burst samplers, 96-bin phase bank, holdover, SSC qualification.
   Not simulated: noise, metastability, mismatch Monte Carlo.
7. Fallback routes `wire_wmon_scope`, `wire_detect_via_wmon`,
   `wire_cdr_external_clock`, `wire_cdr_fpga_oversample` are open
   (integration items); `wire_ctle_bypass` and `wire_board_termination` pass.
